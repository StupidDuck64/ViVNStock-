"""
[src/hisbackfill_1d] VNStock Historical Daily Backfill

Source: DNSE REST API (resolution=1D, no rate limit with API key)
Period: from 2015-01-01 to today

Target table: iceberg.bronze.vnstock_ohlc_1d

Run modes:
  --run-mode init   Full historical load with createOrReplace.
                    Pulls the entire history (--start-date to today).
                    Use for first-time backfill or to rebuild the table.

  --run-mode daily  Smart incremental load using a high-water mark.
                    Queries Iceberg for MAX(time) per symbol and only
                    fetches candles newer than that timestamp.
                    Writes via .append() — safe for scheduled runs.

Usage:
  # Initial load:
  spark-submit vnstock/backfill_1d.py --run-mode init --start-date 2015-01-01

  # Scheduled daily:
  spark-submit vnstock/backfill_1d.py --run-mode daily
"""

import argparse
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, DoubleType,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("vnstock_backfill_1d")

DNSE_CHART_URL = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"

OHLC_DAILY_SCHEMA = StructType([
    StructField("symbol", StringType(), False),
    StructField("time", LongType(), False),
    StructField("open", DoubleType()),
    StructField("high", DoubleType()),
    StructField("low", DoubleType()),
    StructField("close", DoubleType()),
    StructField("volume", LongType()),
    StructField("resolution", StringType()),
    StructField("source", StringType()),
])


def fetch_dnse_daily(symbol: str, from_ts: int, to_ts: int, api_key: str):
    """Fetch daily OHLCV from DNSE REST API (resolution=1D)."""
    params = {"from": from_ts, "to": to_ts, "symbol": symbol, "resolution": "1D"}
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    resp = requests.get(DNSE_CHART_URL, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("t"):
        return None

    import pandas as pd
    pdf = pd.DataFrame({
        "symbol": symbol,
        "time": [int(t) * 1000 for t in data["t"]],  # sec → ms
        "open": [float(v) for v in data["o"]],
        "high": [float(v) for v in data["h"]],
        "low": [float(v) for v in data["l"]],
        "close": [float(v) for v in data["c"]],
        "volume": [int(v) for v in data["v"]],
        "resolution": "1D",
        "source": "DNSE",
    })
    return pdf


def parse_args():
    p = argparse.ArgumentParser(description="VNStock daily backfill (DNSE REST)")
    p.add_argument("--symbols", default=None,
                   help="Comma-separated symbols. Defaults to VNSTOCK_SYMBOLS env var.")
    p.add_argument("--symbols-file", default=None,
                   help="Path to file with comma-separated symbols (overrides --symbols)")
    p.add_argument("--start-date", default="2015-01-01",
                   help="Start date YYYY-MM-DD (default: 2015-01-01)")
    p.add_argument("--batch-size", type=int, default=200,
                   help="Number of symbols per write batch (default: 200)")
    p.add_argument("--workers", type=int, default=20,
                   help="Parallel HTTP fetch workers (default: 20)")
    p.add_argument("--run-mode", choices=["init", "daily"], default="init",
                   help="'init' = full createOrReplace load; 'daily' = incremental append with high-water mark")
    # Keep legacy --mode for backwards compat
    p.add_argument("--mode", choices=["overwrite", "append"], default=None,
                   help="(deprecated, use --run-mode) Write mode")
    return p.parse_args()


def main():
    args = parse_args()

    if args.symbols_file:
        with open(args.symbols_file) as f:
            symbols_str = f.read().strip()
    else:
        symbols_str = args.symbols or os.getenv("VNSTOCK_SYMBOLS", "VCB,HPG,FPT")
    symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]
    if not symbols:
        logger.error("No symbols provided")
        sys.exit(1)

    api_key = os.getenv("DNSE_API_KEY", "")
    if not api_key:
        logger.error("DNSE_API_KEY not set — cannot proceed")
        sys.exit(1)

    spark = SparkSession.builder \
        .appName("VNStock-Backfill-1D") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("INFO")

    spark.sql("CREATE DATABASE IF NOT EXISTS iceberg.bronze")

    # ── Resolve run mode (new --run-mode or legacy --mode) ────────
    if args.run_mode:
        run_mode = args.run_mode
    elif args.mode == "overwrite":
        run_mode = "init"
    elif args.mode == "append":
        run_mode = "daily"
    else:
        run_mode = "init"

    start_date = args.start_date
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    from_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
    to_ts = int(datetime.utcnow().timestamp())

    # ── High-water mark: query Iceberg for MAX(time) per symbol ──
    hwm = {}
    if run_mode == "daily":
        try:
            hwm_rows = spark.sql(
                "SELECT symbol, MAX(time) AS max_ts "
                "FROM iceberg.bronze.vnstock_ohlc_1d "
                "GROUP BY symbol"
            ).collect()
            hwm = {r["symbol"]: int(r["max_ts"]) for r in hwm_rows if r["max_ts"]}
            logger.info("High-water mark loaded for %d symbols (daily mode)", len(hwm))
        except Exception as e:
            logger.warning("HWM query failed (table may not exist yet): %s — falling back to full window", e)

    logger.info("Backfilling 1D for %d symbols | run_mode=%s | workers=%d | %s → %s",
                len(symbols), run_mode, args.workers, start_date, end_date)

    # ── Parallel HTTP fetch ───────────────────────────────────────
    import pandas as pd
    import time as _time

    def _fetch_one(sym):
        try:
            # In daily mode, start from symbol's high-water mark instead of full window
            sym_from_ts = hwm.get(sym, from_ts)
            pdf = fetch_dnse_daily(sym, sym_from_ts, to_ts, api_key)
            return sym, pdf, None
        except Exception as e:
            return sym, None, e

    results = {}
    ok, fail = 0, 0
    t0 = _time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_fetch_one, sym): sym for sym in symbols}
        for i, future in enumerate(as_completed(futures), 1):
            sym, pdf, err = future.result()
            if err:
                logger.warning("[%d/%d] FAILED %s: %s", i, len(symbols), sym, err)
                fail += 1
            elif pdf is not None and not pdf.empty:
                results[sym] = pdf
                ok += 1
            else:
                logger.warning("[%d/%d] No data: %s", i, len(symbols), sym)
                fail += 1
            if i % 100 == 0:
                logger.info("Fetch progress: %d/%d (ok=%d fail=%d)", i, len(symbols), ok, fail)

    logger.info("Fetch complete in %.1fs — ok=%d fail=%d", _time.time() - t0, ok, fail)

    if not results:
        logger.warning("No data collected — nothing to write")
        spark.stop()
        return

    # ── Write to Iceberg in batches ──────────────────────────────
    syms_list = list(results.keys())
    batch_num = 0
    first_write_done = False
    total_rows = 0

    def _write_batch(rows_list):
        nonlocal first_write_done, batch_num
        combined = pd.concat(rows_list, ignore_index=True)
        df = spark.createDataFrame(combined, schema=OHLC_DAILY_SCHEMA)
        df = df.filter(col("time").isNotNull() & (col("time") > 0))
        n = df.count()
        if n == 0:
            return 0
        batch_num += 1
        if run_mode == "init" and not first_write_done:
            logger.info("=== Batch #%d: createOrReplace (%d rows) ===", batch_num, n)
            df.writeTo("iceberg.bronze.vnstock_ohlc_1d") \
                .tableProperty("format-version", "2") \
                .createOrReplace()
        else:
            logger.info("=== Batch #%d: append (%d rows) ===", batch_num, n)
            df.writeTo("iceberg.bronze.vnstock_ohlc_1d").append()
        first_write_done = True
        return n

    for chunk_start in range(0, len(syms_list), args.batch_size):
        chunk = syms_list[chunk_start: chunk_start + args.batch_size]
        rows_list = [results[s] for s in chunk]
        n = _write_batch(rows_list)
        total_rows += n

    logger.info("Backfill 1d DONE — %d symbols OK, %d failed, %d rows written",
                ok, fail, total_rows)
    spark.stop()


if __name__ == "__main__":
    main()

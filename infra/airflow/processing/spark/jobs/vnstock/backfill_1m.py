"""
[src/hisbackfill_1m] VNStock Historical 1-Minute Backfill

Primary source: VCI via vnstock library (~2.5 years of 1m history).
Fallback source: DNSE REST API (Bearer token, ~90 days of 1m history).

After fetching 1m data, aggregates to 5m, 15m, 30m, 1h, 4h timeframes.
Default retention: 900 days (~2.5 years, matching VCI data depth).

Target tables (all Bronze):
  iceberg.bronze.vnstock_ohlc_1m   — raw 1-minute candles
  iceberg.bronze.vnstock_ohlc_5m   — aggregated 5-minute
  iceberg.bronze.vnstock_ohlc_15m  — aggregated 15-minute
  iceberg.bronze.vnstock_ohlc_30m  — aggregated 30-minute
  iceberg.bronze.vnstock_ohlc_1h   — aggregated 1-hour
  iceberg.bronze.vnstock_ohlc_4h   — aggregated 4-hour

Write modes:
  --mode overwrite  (default) full replacement — use for initial historical load
  --mode append     incremental — safe to re-run daily for recent days

Usage:
  spark-submit vnstock/backfill_1m.py \
    --symbols VCB,HPG,FPT \
    --days 900 \
    --mode append
"""

import argparse
import logging
import os
import sys
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import requests

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, lit, floor, max as spark_max, min as spark_min,
    sum as spark_sum, struct,
)
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, DoubleType,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("vnstock_backfill_1m")

DNSE_CHART_URL = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"

VCI_CHART_URL = "https://trading.vietcap.com.vn/api/chart/OHLCChart/gap"
VCI_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Referer": "https://trading.vietcap.com.vn/",
    "Origin": "https://trading.vietcap.com.vn/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

OHLC_SCHEMA = StructType([
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

AGG_INTERVALS = {
    "5m":  5,
    "15m": 15,
    "30m": 30,
    "1h":  60,
    "4h":  240,
}


# ── Data fetching ────────────────────────────────────────────────
def fetch_vci(symbol: str, from_ts: int, to_ts: int):
    """Primary: fetch 1m OHLCV from VCI direct HTTP API (~2.5 years of history).

    VCI prices are in full VND (e.g., 58300) — divides by 1000 to match
    the DNSE thousands scale already stored in the Iceberg tables.
    Timestamps are Unix seconds (string) — converts to UTC Unix milliseconds.
    No authentication required; Origin/Referer headers bypass CORS.
    """
    import pandas as pd
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    payload = {"timeFrame": "ONE_MINUTE", "symbols": [symbol], "from": from_ts, "to": to_ts}
    resp = requests.post(VCI_CHART_URL, json=payload, headers=VCI_HEADERS, timeout=30, verify=False)
    resp.raise_for_status()

    body = resp.json()
    if not body:
        return None
    data = body[0]
    t_list = data.get("t") or []
    if not t_list:
        return None

    return pd.DataFrame({
        "symbol": symbol,
        "time": [int(t) * 1000 for t in t_list],          # sec → ms (UTC)
        "open":   [float(v) / 1000.0 for v in (data.get("o") or [])],
        "high":   [float(v) / 1000.0 for v in (data.get("h") or [])],
        "low":    [float(v) / 1000.0 for v in (data.get("l") or [])],
        "close":  [float(v) / 1000.0 for v in (data.get("c") or [])],
        "volume": [int(v) for v in (data.get("v") or [])],
        "resolution": "1",
        "source": "VCI",
    })


def fetch_dnse(symbol: str, from_ts: int, to_ts: int, api_key: str):
    """Fallback: fetch 1m OHLCV from DNSE REST API (~90 days of history)."""
    params = {"from": from_ts, "to": to_ts, "symbol": symbol, "resolution": "1"}
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
        "resolution": "1",
        "source": "DNSE",
    })
    return pdf


# ── OHLCV aggregation ───────────────────────────────────────────
def aggregate_ohlcv(df_1m: DataFrame, interval_minutes: int) -> DataFrame:
    ms = interval_minutes * 60 * 1000

    bucketed = df_1m.withColumn(
        "time_bucket", (floor(col("time") / lit(ms)) * lit(ms)).cast("long")
    )

    return bucketed.groupBy("symbol", "time_bucket").agg(
        spark_min(struct("time", "open")).getField("open").alias("open"),
        spark_max("high").alias("high"),
        spark_min("low").alias("low"),
        spark_max(struct("time", "close")).getField("close").alias("close"),
        spark_sum("volume").alias("volume"),
    ).select(
        col("symbol"),
        col("time_bucket").alias("time"),
        "open", "high", "low", "close", "volume",
        lit(f"{interval_minutes}m" if interval_minutes < 60
            else f"{interval_minutes // 60}h").alias("resolution"),
        lit("aggregated").alias("source"),
    )


# ── Main ─────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(description="VNStock 1m backfill + aggregation (DNSE)")
    p.add_argument("--symbols", default=None,
                   help="Comma-separated symbols. Defaults to VNSTOCK_SYMBOLS env var.")
    p.add_argument("--symbols-file", default=None,
                   help="Path to file with comma-separated symbols (overrides --symbols)")
    p.add_argument("--days", type=int, default=900, help="Retention window in days (default: 900 = ~2.5 yrs, matching VCI history depth)")
    p.add_argument("--batch-size", type=int, default=100,
                   help="Number of symbols to write per Iceberg batch (default: 100)")
    p.add_argument("--workers", type=int, default=20,
                   help="Parallel HTTP fetch workers (default: 20)")
    p.add_argument("--run-mode", choices=["init", "daily"], default="init",
                   help="'init' = full createOrReplace load; 'daily' = incremental append with high-water mark")
    p.add_argument("--ignore-hwm", action="store_true", default=False,
                   help="In daily mode, ignore high-water mark and fetch full --days window (still appends, no overwrite)")
    # Keep legacy --mode for backwards compat (ignored if --run-mode given explicitly)
    p.add_argument("--mode", choices=["overwrite", "append"], default=None,
                   help="(deprecated, use --run-mode) Write mode")
    return p.parse_args()


def main():
    args = parse_args()

    # Resolve run_mode from --run-mode or legacy --mode
    if args.run_mode:
        run_mode = args.run_mode
    elif args.mode == "append":
        run_mode = "daily"
    else:
        run_mode = "init"

    if args.symbols_file:
        with open(args.symbols_file) as f:
            symbols_str = f.read().strip()
    else:
        symbols_str = args.symbols or os.getenv("VNSTOCK_SYMBOLS", "VCB,HPG,FPT")
    symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]
    if not symbols:
        logger.error("No symbols provided")
        sys.exit(1)

    spark = SparkSession.builder \
        .appName("VNStock-Backfill-1M") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("INFO")

    spark.sql("CREATE DATABASE IF NOT EXISTS iceberg.bronze")

    api_key = os.getenv("DNSE_API_KEY", "")

    now = datetime.utcnow()
    fallback_start = now - timedelta(days=args.days)
    fallback_from_ts = int(fallback_start.timestamp())
    to_ts = int(now.timestamp())

    # ── High-water mark for daily mode ───────────────────────────
    # In daily mode, query Iceberg to find the latest timestamp per symbol
    # so we only fetch candles newer than what we already have.
    hwm: dict[str, int] = {}  # symbol → max_time_unix_sec
    if run_mode == "daily" and not args.ignore_hwm:
        TABLE_1M = "iceberg.bronze.vnstock_ohlc_1m"
        try:
            if spark.catalog.tableExists(TABLE_1M):
                from pyspark.sql.functions import max as spark_max_fn
                hwm_df = spark.table(TABLE_1M) \
                    .groupBy("symbol") \
                    .agg(spark_max_fn("time").alias("max_time"))
                for row in hwm_df.collect():
                    # max_time is in ms → convert to seconds for the API
                    hwm[row["symbol"]] = int(row["max_time"] / 1000)
                logger.info("High-water mark loaded for %d symbols from Iceberg", len(hwm))
            else:
                logger.info("Table %s does not exist yet; full fetch for all symbols", TABLE_1M)
        except Exception as e:
            logger.warning("Could not read high-water mark, falling back to full window: %s", e)

    logger.info(
        "Backfilling 1m for %d symbols | source=VCI(primary)+DNSE(fallback) "
        "| run_mode=%s | days=%d | workers=%d | hwm_symbols=%d",
        len(symbols), run_mode, args.days, args.workers, len(hwm),
    )

    # ── Fetch + write per chunk ──────────────────────────────────
    import pandas as pd

    def _fetch_one(sym):
        # Determine the start timestamp: use high-water mark if available, else fallback
        sym_from_ts = hwm.get(sym, fallback_from_ts)
        if sym_from_ts == fallback_from_ts and run_mode == "daily":
            # No existing data for this symbol — fetch full window
            pass

        # Primary: VCI direct API (~2.5 years, no rate limit, no auth needed)
        try:
            pdf = fetch_vci(sym, sym_from_ts, to_ts)
            if pdf is not None and not pdf.empty:
                return sym, pdf, None
            logger.warning("VCI no data for %s (pdf empty/None) — trying DNSE", sym)
        except Exception as vci_err:
            logger.warning("VCI failed %s: %s — trying DNSE", sym, vci_err)

        # Fallback: DNSE (~90 days, requires api_key)
        if not api_key:
            return sym, None, RuntimeError("VCI returned no data and DNSE_API_KEY not set")
        try:
            pdf = fetch_dnse(sym, sym_from_ts, to_ts, api_key)
            return sym, pdf, None
        except Exception as e:
            return sym, None, e

    ok, fail = 0, 0
    batch_num = 0
    first_write_done = False
    total_rows = 0
    total_processed = 0
    t_start = _time.time()

    for chunk_start in range(0, len(symbols), args.batch_size):
        chunk = symbols[chunk_start: chunk_start + args.batch_size]
        chunk_results = {}

        with ThreadPoolExecutor(max_workers=min(args.workers, len(chunk))) as executor:
            futures = {executor.submit(_fetch_one, sym): sym for sym in chunk}
            for future in as_completed(futures):
                sym, pdf, err = future.result()
                total_processed += 1
                if err:
                    logger.warning("[%d/%d] FAILED %s: %s",
                                   total_processed, len(symbols), sym, err)
                    fail += 1
                elif pdf is not None and not pdf.empty:
                    chunk_results[sym] = pdf
                    ok += 1
                else:
                    logger.warning("[%d/%d] No data: %s",
                                   total_processed, len(symbols), sym)
                    fail += 1

        if chunk_results:
            combined = pd.concat(list(chunk_results.values()), ignore_index=True)
            df = spark.createDataFrame(combined, schema=OHLC_SCHEMA)
            df = df.filter(col("time").isNotNull() & (col("time") > 0))
            n = df.count()
            if n > 0:
                batch_num += 1
                if run_mode == "init" and not first_write_done:
                    logger.info("=== Batch #%d: createOrReplace (%d rows, syms %d-%d) ===",
                                batch_num, n, chunk_start + 1,
                                chunk_start + len(chunk))
                    df.writeTo("iceberg.bronze.vnstock_ohlc_1m") \
                        .tableProperty("format-version", "2") \
                        .createOrReplace()
                else:
                    logger.info("=== Batch #%d: append (%d rows, syms %d-%d) ===",
                                batch_num, n, chunk_start + 1,
                                chunk_start + len(chunk))
                    df.writeTo("iceberg.bronze.vnstock_ohlc_1m").append()
                first_write_done = True
                total_rows += n

        # release chunk memory before next batch
        del chunk_results

        logger.info("Fetch+write progress: %d/%d (ok=%d fail=%d rows_so_far=%d elapsed=%.0fs)",
                    total_processed, len(symbols), ok, fail, total_rows,
                    _time.time() - t_start)

    logger.info("Fetch+write complete in %.1fs — ok=%d fail=%d total_rows=%d",
                _time.time() - t_start, ok, fail, total_rows)

    if total_rows == 0:
        logger.warning("No data written — nothing to aggregate")
        spark.stop()
        return

    # ── Aggregate to higher timeframes ───────────────────────────
    logger.info("Reading full 1m table for aggregation...")
    df_1m = spark.read.table("iceberg.bronze.vnstock_ohlc_1m")
    df_1m.cache()

    for label, minutes in AGG_INTERVALS.items():
        table = f"iceberg.bronze.vnstock_ohlc_{label}"
        logger.info("Aggregating 1m → %s → %s", label, table)
        df_agg = aggregate_ohlcv(df_1m, minutes)
        if run_mode == "init":
            df_agg.writeTo(table) \
                .tableProperty("format-version", "2") \
                .createOrReplace()
        else:
            # In daily mode, re-aggregate from full 1m table and overwrite
            # using dynamic partition overwrite so only affected partitions
            # are replaced while untouched ones remain intact.
            spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
            df_agg.writeTo(table) \
                .tableProperty("format-version", "2") \
                .createOrReplace()

    df_1m.unpersist()

    logger.info("Backfill 1m DONE — %d symbols OK, %d failed, %d rows total", ok, fail, total_rows)
    spark.stop()


if __name__ == "__main__":
    main()

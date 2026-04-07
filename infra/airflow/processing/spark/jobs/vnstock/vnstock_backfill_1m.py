"""
[src/hisbackfill_1m] VNStock Historical 1-Minute Backfill

Primary source: vnstock3 (VCI source, no rate limit)
Backup source:  DNSE REST API (100 req/h, 1000 req/day → ~36s delay)

After fetching 1m data, aggregates to 5m, 15m, 30m, 1h, 4h timeframes.
Retention: 90 days (only backfills the last 90 calendar days).

Target tables (all Bronze):
  iceberg.bronze.vnstock_ohlc_1m   — raw 1-minute candles
  iceberg.bronze.vnstock_ohlc_5m   — aggregated 5-minute
  iceberg.bronze.vnstock_ohlc_15m  — aggregated 15-minute
  iceberg.bronze.vnstock_ohlc_30m  — aggregated 30-minute
  iceberg.bronze.vnstock_ohlc_1h   — aggregated 1-hour
  iceberg.bronze.vnstock_ohlc_4h   — aggregated 4-hour

Usage:
  spark-submit vnstock/vnstock_backfill_1m.py \
    --symbols VCB,HPG,FPT \
    --days 90 \
    --delay 36
"""

import argparse
import logging
import os
import sys
import time as _time
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vnstock_backfill_1m")

# ── Try importing vnstock3 ───────────────────────────────────────
try:
    from vnstock import Vnstock
    HAS_VNSTOCK3 = True
    logger.info("vnstock available — using as primary source (VCI)")
except ImportError:
    try:
        from vnstock3 import Vnstock
        HAS_VNSTOCK3 = True
        logger.info("vnstock3 available — using as primary source")
    except ImportError:
        HAS_VNSTOCK3 = False
        logger.warning("vnstock not installed — DNSE REST API only")

DNSE_CHART_URL = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"

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
def fetch_vnstock3(symbol: str, start_date: str, end_date: str):
    """Primary: fetch 1m OHLCV from vnstock3 (VCI source)."""
    stock = Vnstock().stock(symbol=symbol, source="VCI")
    pdf = stock.quote.history(start=start_date, end=end_date, interval="1m")
    if pdf is None or pdf.empty:
        return None
    # Normalize column names: vnstock3 may use 'ticker' instead of 'symbol'
    rename_map = {"ticker": "symbol", "code": "symbol"}
    for old, new in rename_map.items():
        if old in pdf.columns and new not in pdf.columns:
            pdf = pdf.rename(columns={old: new})
    if "symbol" not in pdf.columns:
        pdf["symbol"] = symbol
    # Ensure 'time' column is epoch ms
    if "time" in pdf.columns:
        if hasattr(pdf["time"].iloc[0], "timestamp"):
            pdf["time"] = (pdf["time"].astype("int64") // 10**6)
    pdf["source"] = "vnstock3"
    pdf["resolution"] = "1"
    return pdf[["symbol", "time", "open", "high", "low", "close", "volume",
                 "resolution", "source"]]


def fetch_dnse(symbol: str, from_ts: int, to_ts: int, api_key: str):
    """Backup: fetch 1m OHLCV from DNSE REST API (TradingView-compatible)."""
    params = {"from": from_ts, "to": to_ts, "symbol": symbol, "resolution": "1"}
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    resp = requests.get(DNSE_CHART_URL, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # DNSE returns {"t":[], "o":[], "h":[], "l":[], "c":[], "v":[]}
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
    """
    Aggregate 1m candles to a higher timeframe.

    Uses struct min/max trick for deterministic first-open / last-close:
      - open = open of the candle with smallest timestamp in the bucket
      - close = close of the candle with largest timestamp in the bucket
    """
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
    p = argparse.ArgumentParser(description="VNStock 1m backfill + aggregation")
    p.add_argument("--symbols", required=True, help="Comma-separated symbols")
    p.add_argument("--days", type=int, default=90, help="Retention window in days")
    p.add_argument("--delay", type=int, default=36,
                   help="Delay (seconds) between DNSE API requests")
    return p.parse_args()


def main():
    args = parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if not symbols:
        logger.error("No symbols provided")
        sys.exit(1)

    spark = SparkSession.builder \
        .appName("VNStock-Backfill-1M") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    spark.sql("CREATE DATABASE IF NOT EXISTS iceberg.bronze")

    api_key = os.getenv("DNSE_API_KEY", "")
    now = datetime.utcnow()
    start = now - timedelta(days=args.days)
    start_str = start.strftime("%Y-%m-%d")
    end_str = now.strftime("%Y-%m-%d")
    from_ts = int(start.timestamp())
    to_ts = int(now.timestamp())

    all_rows = []
    ok, fail = 0, 0

    for i, sym in enumerate(symbols):
        logger.info("[%d/%d] Fetching 1m for %s", i + 1, len(symbols), sym)
        pdf = None

        # Primary: vnstock3
        if HAS_VNSTOCK3:
            try:
                pdf = fetch_vnstock3(sym, start_str, end_str)
                if pdf is not None and not pdf.empty:
                    logger.info("  vnstock3 OK: %d rows", len(pdf))
            except Exception as e:
                logger.warning("  vnstock3 failed for %s: %s", sym, e)
                pdf = None

        # Backup: DNSE REST API
        if pdf is None or pdf.empty:
            if not api_key:
                logger.warning("  No DNSE_API_KEY, skipping %s", sym)
                fail += 1
                continue
            try:
                pdf = fetch_dnse(sym, from_ts, to_ts, api_key)
                if pdf is not None and not pdf.empty:
                    logger.info("  DNSE OK: %d rows", len(pdf))
                if args.delay > 0:
                    _time.sleep(args.delay)
            except Exception as e:
                logger.error("  DNSE also failed for %s: %s", sym, e)
                fail += 1
                continue

        if pdf is None or pdf.empty:
            logger.warning("  No data for %s", sym)
            fail += 1
            continue

        all_rows.append(pdf)
        ok += 1

    logger.info("Fetched %d symbols OK, %d failed", ok, fail)
    if not all_rows:
        logger.warning("No data collected — nothing to write")
        spark.stop()
        return

    import pandas as pd
    combined_pdf = pd.concat(all_rows, ignore_index=True)
    df_1m = spark.createDataFrame(combined_pdf, schema=OHLC_SCHEMA)
    df_1m = df_1m.filter(col("time").isNotNull() & (col("time") > 0))
    df_1m.cache()

    row_count = df_1m.count()
    logger.info("Total 1m rows: %d", row_count)
    if row_count == 0:
        spark.stop()
        return

    # Write 1m raw data
    logger.info("Writing 1m → iceberg.bronze.vnstock_ohlc_1m")
    df_1m.writeTo("iceberg.bronze.vnstock_ohlc_1m") \
        .tableProperty("format-version", "2") \
        .createOrReplace()

    # Aggregate and write higher timeframes
    for label, minutes in AGG_INTERVALS.items():
        table = f"iceberg.bronze.vnstock_ohlc_{label}"
        logger.info("Aggregating 1m → %s → %s", label, table)
        df_agg = aggregate_ohlcv(df_1m, minutes)
        df_agg.writeTo(table) \
            .tableProperty("format-version", "2") \
            .createOrReplace()

    df_1m.unpersist()
    logger.info("Backfill 1m complete: %d symbols, %d rows", ok, row_count)
    spark.stop()


if __name__ == "__main__":
    main()

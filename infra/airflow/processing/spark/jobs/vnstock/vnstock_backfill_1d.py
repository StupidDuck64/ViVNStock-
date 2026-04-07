"""
[src/hisbackfill_1d] VNStock Historical Daily Backfill

Source: vnstock3 (TCBS source, no rate limit)
Period: from 2015-01-01 to today
Write mode: overwritePartitions() — idempotent daily refresh

Target table: iceberg.gold.vnstock_ohlc_1d

Usage:
  spark-submit vnstock/vnstock_backfill_1d.py \
    --symbols VCB,HPG,FPT \
    --start-date 2015-01-01
"""

import argparse
import logging
import os
import sys
from datetime import datetime

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, to_date
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, DoubleType,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vnstock_backfill_1d")

try:
    from vnstock import Vnstock
    HAS_VNSTOCK3 = True
    logger.info("vnstock available (VCI source)")
except ImportError:
    try:
        from vnstock3 import Vnstock
        HAS_VNSTOCK3 = True
        logger.info("vnstock3 available")
    except ImportError:
        HAS_VNSTOCK3 = False
        logger.error("vnstock not installed — required for daily backfill")

OHLC_DAILY_SCHEMA = StructType([
    StructField("symbol", StringType(), False),
    StructField("time", LongType(), False),
    StructField("open", DoubleType()),
    StructField("high", DoubleType()),
    StructField("low", DoubleType()),
    StructField("close", DoubleType()),
    StructField("volume", LongType()),
    StructField("source", StringType()),
])


def fetch_daily_vnstock3(symbol: str, start_date: str, end_date: str):
    """Fetch daily OHLCV from vnstock VCI source."""
    stock = Vnstock().stock(symbol=symbol, source="VCI")
    pdf = stock.quote.history(start=start_date, end=end_date, interval="1D")
    if pdf is None or pdf.empty:
        return None

    # Normalize columns
    rename_map = {"ticker": "symbol", "code": "symbol",
                  "tradingDate": "time", "date": "time"}
    for old, new in rename_map.items():
        if old in pdf.columns and new not in pdf.columns:
            pdf = pdf.rename(columns={old: new})
    if "symbol" not in pdf.columns:
        pdf["symbol"] = symbol

    # Convert time to epoch ms
    if "time" in pdf.columns:
        if hasattr(pdf["time"].iloc[0], "timestamp"):
            pdf["time"] = (pdf["time"].astype("int64") // 10**6)
        elif isinstance(pdf["time"].iloc[0], str):
            import pandas as pd
            pdf["time"] = (pd.to_datetime(pdf["time"]).astype("int64") // 10**6)

    pdf["source"] = "TCBS"
    cols = ["symbol", "time", "open", "high", "low", "close", "volume", "source"]
    for c in cols:
        if c not in pdf.columns:
            pdf[c] = None
    return pdf[cols]


def parse_args():
    p = argparse.ArgumentParser(description="VNStock daily backfill (vnstock3 TCBS)")
    p.add_argument("--symbols", default=None,
                   help="Comma-separated symbols. Defaults to VNSTOCK_SYMBOLS env var.")
    p.add_argument("--start-date", default="2015-01-01",
                   help="Start date YYYY-MM-DD (default: 2015-01-01)")
    return p.parse_args()


def main():
    args = parse_args()

    if not HAS_VNSTOCK3:
        logger.error("vnstock3 is required for daily backfill. Install: pip install vnstock3")
        sys.exit(1)

    symbols_str = args.symbols or os.getenv("VNSTOCK_SYMBOLS", "VCB,HPG,FPT")
    symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]
    if not symbols:
        logger.error("No symbols provided")
        sys.exit(1)

    spark = SparkSession.builder \
        .appName("VNStock-Backfill-1D") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    spark.sql("CREATE DATABASE IF NOT EXISTS iceberg.gold")

    start_date = args.start_date
    end_date = datetime.utcnow().strftime("%Y-%m-%d")

    all_rows = []
    ok, fail = 0, 0

    for i, sym in enumerate(symbols):
        logger.info("[%d/%d] Fetching daily for %s (%s → %s)",
                     i + 1, len(symbols), sym, start_date, end_date)
        try:
            pdf = fetch_daily_vnstock3(sym, start_date, end_date)
            if pdf is not None and not pdf.empty:
                all_rows.append(pdf)
                ok += 1
                logger.info("  OK: %d rows", len(pdf))
            else:
                logger.warning("  No data for %s", sym)
                fail += 1
        except Exception as e:
            logger.error("  Failed for %s: %s", sym, e)
            fail += 1

    logger.info("Fetched %d symbols OK, %d failed", ok, fail)
    if not all_rows:
        logger.warning("No data collected — nothing to write")
        spark.stop()
        return

    import pandas as pd
    combined_pdf = pd.concat(all_rows, ignore_index=True)
    df = spark.createDataFrame(combined_pdf, schema=OHLC_DAILY_SCHEMA)
    df = df.filter(col("time").isNotNull() & (col("time") > 0))

    # Add partition column (trade_date) for efficient overwrite
    df = df.withColumn(
        "trade_date",
        to_date((col("time") / lit(1000)).cast("timestamp"))
    )

    row_count = df.count()
    logger.info("Total daily rows: %d", row_count)

    # Write with overwritePartitions() — idempotent
    logger.info("Writing → iceberg.gold.vnstock_ohlc_1d (overwritePartitions)")
    df.sortWithinPartitions("symbol", "time") \
        .writeTo("iceberg.gold.vnstock_ohlc_1d") \
        .tableProperty("format-version", "2") \
        .partitionedBy(col("trade_date")) \
        .createOrReplace()

    logger.info("Backfill 1d complete: %d symbols, %d rows", ok, row_count)
    spark.stop()


if __name__ == "__main__":
    main()

"""
[src/gold_daily_summary] VNStock Gold — Daily Summary Table

Reads daily OHLCV data from bronze, computes:
  - prev_close (LAG window)
  - change     = close - prev_close
  - change_pct = (close - prev_close) / prev_close * 100
  - sector / industry mapping (Vietnamese market ICB-based)

Writes to: iceberg.gold.vnstock_daily_summary
Partitioned by: trade_date

This table feeds PriceBoard (Top Movers) and SectorHeatmap directly,
eliminating ad-hoc computation in the frontend/API layer.

Usage:
  spark-submit vnstock/gold_daily_summary.py
  spark-submit vnstock/gold_daily_summary.py --source-table iceberg.bronze.vnstock_ohlc_1d
  spark-submit vnstock/gold_daily_summary.py --mode incremental --days 5
"""

import argparse
import logging
from datetime import datetime, timedelta

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import StringType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("gold_daily_summary")

# ─── Vietnamese market sector mapping (ICB-based) ───
# Matches frontend SectorHeatmap SECTOR_MAP for consistency
SECTOR_MAP = {
    "Ngân hàng": [
        "VCB", "BID", "CTG", "TCB", "MBB", "ACB", "VPB", "HDB", "STB",
        "TPB", "SHB", "MSB", "LPB", "EIB", "OCB", "SSB", "ABB", "NAB",
        "BAB", "BVB", "KLB", "PGB", "VIB", "VBB", "NVB",
    ],
    "Bất động sản": [
        "VHM", "VIC", "NVL", "KDH", "DXG", "NLG", "HDG", "PDR", "DIG",
        "BCG", "CEO", "LDG", "NBB", "SCR", "TDH", "IJC", "HDC", "CII",
        "KBC", "ITA", "SZC", "AGG", "NTL", "API",
    ],
    "Chứng khoán": [
        "SSI", "VND", "HCM", "VCI", "SHS", "MBS", "FTS", "CTS", "AGR",
        "BSI", "DSC", "ORS", "TVS", "BVS", "APS", "EVF",
    ],
    "Thép": [
        "HPG", "HSG", "NKG", "POM", "TLH", "TVN", "DTL", "SMC", "VGS", "TIS",
    ],
    "Công nghệ": [
        "FPT", "CMG", "VGI", "FOX", "SAM", "ELC", "ITD", "ONE", "POT", "VTC",
    ],
    "Thực phẩm & Đồ uống": [
        "VNM", "MSN", "SAB", "KDC", "QNS", "MCH", "SBT", "LSS", "TAC",
        "ABT", "AAM", "BBC", "BHN", "HAD",
    ],
    "Dầu khí": [
        "GAS", "PLX", "PVS", "PVD", "BSR", "OIL", "PVB", "PVC", "COM", "PGS", "PVP",
    ],
    "Điện": [
        "POW", "GEG", "REE", "PC1", "NT2", "HND", "PPC", "SBA", "VSH",
        "TMP", "CHP", "SHP", "TBC",
    ],
    "Bảo hiểm": [
        "BVH", "BMI", "BIC", "MIG", "PVI", "PRE", "ABI", "PTI",
    ],
    "Hóa chất & Phân bón": [
        "DPM", "DCM", "DGC", "CSV", "LAS", "BFC", "NFC", "HVT", "PMB",
    ],
    "Vận tải & Logistics": [
        "VTP", "GMD", "VOS", "HAH", "MVN", "TMS", "VNA", "SGP", "VNS", "TCL",
    ],
    "Xây dựng": [
        "CTD", "HBC", "VCG", "ROS", "HUT", "C47", "FCN", "LCG", "CKG", "TV2",
    ],
    "Bán lẻ": [
        "MWG", "PNJ", "DGW", "FRT", "PET", "AST",
    ],
    "Dệt may": [
        "TCM", "STK", "TNG", "GMC", "VGT", "MSH", "GIL", "ADS", "EVE",
    ],
    "Cao su & Gỗ": [
        "GVR", "PHR", "DPR", "TRC", "BRC", "HRC", "SRF", "TNC", "PTB", "TTF",
    ],
    "Thủy sản": [
        "VHC", "ANV", "IDI", "ACL", "CMX", "FMC", "MPC", "TS4",
    ],
}

# Invert: symbol → sector
_SYMBOL_SECTOR = {}
for sector, symbols in SECTOR_MAP.items():
    for sym in symbols:
        _SYMBOL_SECTOR[sym] = sector


def _lookup_sector(symbol: str) -> str:
    """Return sector name for symbol, or 'Khác' (Other) if unmapped."""
    return _SYMBOL_SECTOR.get(symbol, "Khác")


def parse_args():
    p = argparse.ArgumentParser(description="Gold daily summary builder")
    p.add_argument(
        "--source-table",
        default="iceberg.bronze.vnstock_ohlc_1d",
        help="Source Iceberg table with daily OHLCV (default: iceberg.bronze.vnstock_ohlc_1d)",
    )
    p.add_argument(
        "--target-table",
        default="iceberg.gold.vnstock_daily_summary",
        help="Target Gold table (default: iceberg.gold.vnstock_daily_summary)",
    )
    p.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="full",
        help="'full' rebuilds entire table; 'incremental' only processes last N days",
    )
    p.add_argument(
        "--days",
        type=int,
        default=5,
        help="Number of days to process in incremental mode (default: 5)",
    )
    return p.parse_args()


def main():
    args = parse_args()

    spark = SparkSession.builder \
        .appName("VNStock-Gold-DailySummary") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    spark.sql("CREATE DATABASE IF NOT EXISTS iceberg.gold")

    # ── Register sector UDF ──
    sector_udf = F.udf(_lookup_sector, StringType())

    # ── Read source ──
    logger.info("Reading source: %s", args.source_table)
    try:
        df = spark.table(args.source_table)
    except Exception as e:
        logger.error("Cannot read source table: %s", e)
        spark.stop()
        return

    total = df.count()
    logger.info("Source rows: %d", total)
    if total == 0:
        logger.warning("Source table empty — nothing to process")
        spark.stop()
        return

    # ── Add trade_date column ──
    df = df.withColumn(
        "trade_date",
        F.to_date((F.col("time") / F.lit(1000)).cast("timestamp")),
    )

    # ── In incremental mode, filter to last N days ──
    if args.mode == "incremental":
        cutoff = datetime.utcnow() - timedelta(days=args.days + 2)  # +2 for prev_close window
        cutoff_ms = int(cutoff.timestamp() * 1000)
        logger.info("Incremental mode: processing data since %s (cutoff_ms=%d)", cutoff, cutoff_ms)
        df = df.filter(F.col("time") >= cutoff_ms)

    # ── Deduplicate: keep latest per (symbol, trade_date) ──
    if "ingest_timestamp" in df.columns:
        w_dedup = Window.partitionBy("symbol", "trade_date").orderBy(F.col("ingest_timestamp").desc())
    else:
        w_dedup = Window.partitionBy("symbol", "trade_date").orderBy(F.col("time").desc())
    df = df.withColumn("_rn", F.row_number().over(w_dedup)) \
           .filter(F.col("_rn") == 1) \
           .drop("_rn")

    # ── Compute prev_close, change, change_pct using LAG window ──
    w_lag = Window.partitionBy("symbol").orderBy("trade_date")
    df = df.withColumn("prev_close", F.lag("close", 1).over(w_lag))
    df = df.withColumn(
        "change",
        F.when(F.col("prev_close").isNotNull(), F.col("close") - F.col("prev_close")).otherwise(F.lit(0.0)),
    )
    df = df.withColumn(
        "change_pct",
        F.when(
            (F.col("prev_close").isNotNull()) & (F.col("prev_close") > 0),
            F.round((F.col("close") - F.col("prev_close")) / F.col("prev_close") * 100, 2),
        ).otherwise(F.lit(0.0)),
    )

    # ── Ceiling / Floor prices (±7% for HOSE/HNX, ±15% for UPCOM) ──
    df = df.withColumn(
        "ref_price",
        F.when(F.col("prev_close").isNotNull(), F.col("prev_close")).otherwise(F.col("close")),
    )
    df = df.withColumn("ceiling_price", F.round(F.col("ref_price") * 1.07, 2))
    df = df.withColumn("floor_price", F.round(F.col("ref_price") * 0.93, 2))

    # ── Add sector mapping ──
    df = df.withColumn("sector", sector_udf(F.col("symbol")))

    # ── Select final columns ──
    gold_df = df.select(
        "symbol",
        "trade_date",
        F.col("open").cast("double"),
        F.col("high").cast("double"),
        F.col("low").cast("double"),
        F.col("close").cast("double"),
        F.col("volume").cast("long"),
        F.col("prev_close").cast("double"),
        F.col("change").cast("double"),
        F.col("change_pct").cast("double"),
        F.col("ref_price").cast("double"),
        F.col("ceiling_price").cast("double"),
        F.col("floor_price").cast("double"),
        "sector",
    )

    # ── In incremental mode, only write the last N days ──
    if args.mode == "incremental":
        cutoff_date = (datetime.utcnow() - timedelta(days=args.days)).strftime("%Y-%m-%d")
        gold_df = gold_df.filter(F.col("trade_date") >= cutoff_date)

    row_count = gold_df.count()
    logger.info("Gold rows to write: %d", row_count)

    # ── Write to Gold Iceberg table ──
    logger.info("Writing → %s (mode=%s)", args.target_table, args.mode)
    gold_df = gold_df.repartition("trade_date").sortWithinPartitions("symbol", "trade_date")

    if args.mode == "full":
        gold_df.writeTo(args.target_table) \
            .tableProperty("format-version", "2") \
            .partitionedBy(F.col("trade_date")) \
            .createOrReplace()
    else:
        # Incremental: MERGE or overwrite partitions
        gold_df.writeTo(args.target_table) \
            .overwritePartitions()

    logger.info("Gold daily summary complete: %d rows written (mode=%s)", row_count, args.mode)
    spark.stop()


if __name__ == "__main__":
    main()

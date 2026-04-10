import argparse
import logging

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, row_number
from pyspark.sql.window import Window

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vnstock_compact")


def parse_args():
    p = argparse.ArgumentParser(description="VNStock Bronze → Silver compaction")
    p.add_argument("--bronze-table", required=True,
                   help="Source Bronze Iceberg table (e.g. iceberg.bronze.vnstock_ohlc_stock)")
    p.add_argument("--silver-table", required=True,
                   help="Target Silver Iceberg table (e.g. iceberg.silver.vnstock_ohlc_stock)")
    p.add_argument("--dedup-keys", default="symbol,time",
                   help="Comma-separated dedup key columns (default: symbol,time)")
    p.add_argument("--order-col", default="ingest_timestamp",
                   help="Column to determine recency for dedup (default: ingest_timestamp)")
    return p.parse_args()


def main():
    args = parse_args()
    dedup_keys = [k.strip() for k in args.dedup_keys.split(",")]

    spark = SparkSession.builder \
        .appName(f"VNStock-Compact-{args.bronze_table.split('.')[-1]}") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    spark.sql("CREATE DATABASE IF NOT EXISTS iceberg.silver")

    # Read Bronze
    logger.info("Reading %s", args.bronze_table)
    df = spark.table(args.bronze_table)
    total = df.count()
    logger.info("Bronze rows: %d", total)

    if total == 0:
        logger.warning("Bronze table is empty — nothing to compact")
        spark.stop()
        return

    # Deduplicate: keep the row with the latest ingest_timestamp per dedup key group
    has_order_col = args.order_col in df.columns
    if has_order_col:
        w = Window.partitionBy(*dedup_keys).orderBy(col(args.order_col).desc())
        deduped = df.withColumn("_rn", row_number().over(w)) \
                     .filter(col("_rn") == 1) \
                     .drop("_rn")
    else:
        logger.warning("Order column '%s' not found — using dropDuplicates", args.order_col)
        deduped = df.dropDuplicates(dedup_keys)

    # Drop internal columns that shouldn't propagate to Silver
    drop_cols = ["topic", "kafka_timestamp"]
    for c in drop_cols:
        if c in deduped.columns:
            deduped = deduped.drop(c)

    dedup_count = deduped.count()
    logger.info("After dedup: %d rows (removed %d duplicates)", dedup_count, total - dedup_count)

    # Repartition by symbol — each file stores exactly 1 symbol
    if "symbol" in deduped.columns:
        deduped = deduped.repartition(col("symbol")).sortWithinPartitions("symbol", "time")
    else:
        logger.warning("No 'symbol' column — skipping repartition by symbol")

    # Write to Silver (overwritePartitions for idempotent re-runs)
    logger.info("Writing → %s", args.silver_table)
    deduped.writeTo(args.silver_table) \
        .tableProperty("format-version", "2") \
        .createOrReplace()

    logger.info("Compaction complete: %s → %s (%d rows)",
                args.bronze_table, args.silver_table, dedup_count)
    spark.stop()


if __name__ == "__main__":
    main()

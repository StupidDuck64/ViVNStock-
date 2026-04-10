import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, lit, floor, row_number,
    max as spark_max, min as spark_min, sum as spark_sum, struct,
)
from pyspark.sql.window import Window

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vnstock_dedup_1m")

AGG_INTERVALS = {
    "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240,
}


def aggregate_ohlcv(df_1m, interval_minutes):
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


def main():
    spark = SparkSession.builder \
        .appName("VNStock-Dedup-1M") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    logger.info("Reading bronze.vnstock_ohlc_1m...")
    df = spark.read.table("iceberg.bronze.vnstock_ohlc_1m")
    total_before = df.count()
    logger.info("Total rows BEFORE dedup: %d", total_before)

    # Deduplicate: keep one row per (symbol, time), prefer the row with highest volume
    w = Window.partitionBy("symbol", "time").orderBy(col("volume").desc())
    deduped = df.withColumn("rn", row_number().over(w)).filter(col("rn") == 1).drop("rn")
    total_after = deduped.count()
    removed = total_before - total_after
    logger.info("Total rows AFTER dedup: %d (removed %d duplicates)", total_after, removed)

    if removed == 0:
        logger.info("No duplicates found. Nothing to do.")
        spark.stop()
        return

    # Rewrite the table (createOrReplace to atomic-swap)
    logger.info("Rewriting bronze.vnstock_ohlc_1m (atomic replace)...")
    deduped.writeTo("iceberg.bronze.vnstock_ohlc_1m") \
        .tableProperty("format-version", "2") \
        .createOrReplace()
    logger.info("Table rewritten successfully.")

    # Re-aggregate all higher timeframes
    logger.info("Re-reading 1m table for aggregation...")
    df_1m = spark.read.table("iceberg.bronze.vnstock_ohlc_1m")
    df_1m.cache()

    for label, minutes in AGG_INTERVALS.items():
        table = f"iceberg.bronze.vnstock_ohlc_{label}"
        logger.info("Aggregating 1m → %s → %s", label, table)
        df_agg = aggregate_ohlcv(df_1m, minutes)
        df_agg.writeTo(table) \
            .tableProperty("format-version", "2") \
            .createOrReplace()

    df_1m.unpersist()

    logger.info("Dedup complete: removed %d duplicates, re-aggregated all timeframes.", removed)
    spark.stop()


if __name__ == "__main__":
    main()

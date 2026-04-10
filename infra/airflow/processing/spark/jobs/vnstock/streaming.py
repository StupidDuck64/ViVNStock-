import json
import logging
import os

import redis
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, DoubleType,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("vnstock_streaming")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Schema used AFTER Avro decode (matches the Avro record fields exactly)
TICK_SCHEMA = StructType([
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


# ─── Redis write helper ─────────────────────────────────────────
def _redis_client():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True,
                       socket_connect_timeout=5)


def write_batch(batch_df, batch_id):
    """
    Process each micro-batch:
      1. Deduplicate by (symbol, time) within the batch
      2. Filter out rows already written (tracked in Redis hash)
      3. Append only NEW rows to Iceberg bronze.vnstock_ohlc_1m
      4. Write latest tick per symbol to Redis
    """
    if batch_df.isEmpty():
        return

    # Deduplicate within batch: keep one row per (symbol, time) pair
    deduped = batch_df.dropDuplicates(["symbol", "time"])

    row_count = deduped.count()
    if row_count == 0:
        return

    # ── Filter out already-written timestamps using Redis ──
    # Redis hash key: vnstock:stream:last_ts — maps symbol → last written timestamp
    try:
        r = _redis_client()
        all_rows = deduped.collect()

        # Check which rows are actually new
        new_rows = []
        pipe = r.pipeline()
        for row in all_rows:
            pipe.hget("vnstock:stream:last_ts", row["symbol"])
        last_timestamps = pipe.execute()

        for row, last_ts in zip(all_rows, last_timestamps):
            last_ts_val = int(last_ts) if last_ts else 0
            if row["time"] > last_ts_val:
                new_rows.append(row)

        if not new_rows:
            logger.info("Batch %d: %d rows all duplicates, skipping Iceberg write", batch_id, row_count)
            # Still update Redis ticks for serving
            _update_redis_ticks(r, all_rows, batch_id)
            return

        # Create DataFrame from new rows only
        new_df = deduped.sparkSession.createDataFrame(new_rows, deduped.schema)

    except redis.ConnectionError as e:
        logger.warning("Batch %d: Redis dedup check failed (%s), writing all rows", batch_id, e)
        new_df = deduped
        new_rows = None  # Flag to skip Redis timestamp update
        r = None

    # ── 1. Write to Iceberg (append mode) — only new rows ──
    try:
        iceberg_df = new_df.select(
            "symbol", "time", "open", "high", "low", "close", "volume",
            "resolution", "source"
        )
        iceberg_df.writeTo("iceberg.bronze.vnstock_ohlc_1m").append()
        new_count = new_df.count()
        logger.info("Batch %d: %d new rows → Iceberg (filtered %d duplicates)",
                     batch_id, new_count, row_count - new_count)
    except Exception as e:
        logger.error("Batch %d: Iceberg write failed: %s", batch_id, e)
        return

    # ── 2. Update Redis: ticks for serving + last_ts for dedup tracking ──
    try:
        if r is None:
            r = _redis_client()

        # Update dedup tracking hash
        if new_rows:
            pipe = r.pipeline()
            for row in (new_rows if new_rows else []):
                pipe.hset("vnstock:stream:last_ts", row["symbol"], str(row["time"]))
            pipe.execute()

        # Update tick data for frontend serving
        _update_redis_ticks(r, deduped.collect(), batch_id)

    except redis.ConnectionError as e:
        logger.error("Batch %d: Redis update failed: %s", batch_id, e)


def _update_redis_ticks(r, rows, batch_id):
    """Write latest tick per symbol to Redis for real-time frontend serving."""
    try:
        pipe = r.pipeline()
        for row in rows:
            sym = row["symbol"]
            if not sym:
                continue
            data = {
                "symbol": sym,
                "time": row["time"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
                "resolution": row["resolution"],
            }
            pipe.set(f"vnstock:tick:{sym}", json.dumps(data))
            pipe.zadd("vnstock:ticks:all", {sym: row["time"] or 0})
        pipe.execute()
        logger.info("Batch %d: %d ticks → Redis", batch_id, len(rows))
    except redis.ConnectionError as e:
        logger.error("Batch %d: Redis tick write failed: %s", batch_id, e)


# ─── Main ────────────────────────────────────────────────────────
def main():
    spark = SparkSession.builder \
        .appName("VNStock-Streaming-Kafka-To-Iceberg") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("INFO")

    # Ensure database exists
    spark.sql("CREATE DATABASE IF NOT EXISTS iceberg.bronze")

    kafka_bs = os.getenv("KAFKA_BOOTSTRAP_SERVERS",
                         spark.conf.get("spark.dataforge.kafka.bootstrap", "kafka:9092"))
    kafka_topic = os.getenv("KAFKA_TOPIC", "vnstock.ohlc.realtime")
    schema_registry_url = os.getenv(
        "SCHEMA_REGISTRY_URL",
        spark.conf.get("spark.dataforge.schema.registry", "http://schema-registry:8081"),
    )

    logger.info("Starting streaming: Kafka(%s/%s) → Iceberg + Redis [Avro, Schema Registry: %s]",
                kafka_bs, kafka_topic, schema_registry_url)

    # Read raw bytes from Kafka (Confluent Avro wire format)
    raw_stream = spark.readStream.format("kafka") \
        .option("kafka.bootstrap.servers", kafka_bs) \
        .option("subscribe", kafka_topic) \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()

    # Avro deserialization UDF using spark_utils (distributed via --py-files)
    from spark_utils import decode_confluent_avro
    decode_udf = F.udf(
        lambda value: decode_confluent_avro(value, schema_registry_url),
        StringType(),
    )

    # Decode Avro bytes → JSON string → struct → typed fields
    parsed = raw_stream.select(
        F.from_json(decode_udf(F.col("value")), TICK_SCHEMA).alias("tick")
    ).select("tick.*").filter(
        F.col("symbol").isNotNull() & F.col("time").isNotNull()
    )

    # Write stream using foreachBatch (Iceberg + Redis)
    # Trigger interval: 1 second — minimum practical for Iceberg sink.
    # Going below 1s causes excessive small Parquet files on MinIO (small files problem).
    # Redis latency is already <100ms via direct producer write; this path is backup.
    query = parsed.writeStream \
        .foreachBatch(write_batch) \
        .option("checkpointLocation", "s3a://checkpoints/spark/vnstock/streaming/ohlc") \
        .trigger(processingTime="1 seconds") \
        .start()

    logger.info("Streaming query started — processing every 1 second")
    query.awaitTermination()


if __name__ == "__main__":
    main()

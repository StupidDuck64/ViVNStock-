"""
[src/batch] VNStock Bronze Ingest: Kafka → Iceberg Bronze

Reads from VNStock Kafka topics (Avro-encoded with Confluent wire format)
and writes raw data into Iceberg Bronze tables.

Avro deserialization:
  1. Strip 5-byte Confluent header: substring(value, 6)
  2. Parse Avro binary via from_avro() with embedded schema

Uses AvailableNow trigger (bounded streaming) matching lakehouse-oss pattern.

Usage:
  spark-submit vnstock/vnstock_bronze_stream.py \
    --topic ohlc_stock \
    --table iceberg.bronze.vnstock_ohlc_stock \
    --checkpoint s3a://checkpoints/spark/iceberg/bronze/vnstock_ohlc_stock
"""

import argparse
import json
import logging

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, expr
from pyspark.sql.avro.functions import from_avro

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vnstock_bronze")

# ─── Avro Schema JSON strings (embedded, matching .avsc files) ───
AVRO_SCHEMAS = {
    "ohlc_stock": json.dumps({
        "type": "record", "name": "OhlcStock", "namespace": "com.vnstock.avro",
        "fields": [
            {"name": "symbol", "type": "string"},
            {"name": "time", "type": "long"},
            {"name": "open", "type": "double"},
            {"name": "high", "type": "double"},
            {"name": "low", "type": "double"},
            {"name": "close", "type": "double"},
            {"name": "volume", "type": "long"},
            {"name": "resolution", "type": "string"},
            {"name": "lastUpdated", "type": "long"},
            {"name": "source", "type": "string", "default": "DNSE"},
            {"name": "ingest_timestamp", "type": "long"}
        ]
    }),
    "ohlc_derivative": json.dumps({
        "type": "record", "name": "OhlcDerivative", "namespace": "com.vnstock.avro",
        "fields": [
            {"name": "symbol", "type": "string"},
            {"name": "time", "type": "long"},
            {"name": "open", "type": "double"},
            {"name": "high", "type": "double"},
            {"name": "low", "type": "double"},
            {"name": "close", "type": "double"},
            {"name": "volume", "type": "long"},
            {"name": "resolution", "type": "string"},
            {"name": "lastUpdated", "type": "long"},
            {"name": "source", "type": "string", "default": "DNSE"},
            {"name": "ingest_timestamp", "type": "long"}
        ]
    }),
    "ohlc_index": json.dumps({
        "type": "record", "name": "OhlcIndex", "namespace": "com.vnstock.avro",
        "fields": [
            {"name": "symbol", "type": "string"},
            {"name": "time", "type": "long"},
            {"name": "open", "type": "double"},
            {"name": "high", "type": "double"},
            {"name": "low", "type": "double"},
            {"name": "close", "type": "double"},
            {"name": "volume", "type": "long"},
            {"name": "resolution", "type": "string"},
            {"name": "lastUpdated", "type": "long"},
            {"name": "source", "type": "string", "default": "DNSE"},
            {"name": "ingest_timestamp", "type": "long"}
        ]
    }),
    "quote": json.dumps({
        "type": "record", "name": "Quote", "namespace": "com.vnstock.avro",
        "fields": [
            {"name": "symbol", "type": "string"},
            {"name": "marketId", "type": "string"},
            {"name": "boardId", "type": "string"},
            {"name": "bid", "type": {"type": "array", "items": {
                "type": "record", "name": "PriceLevel",
                "fields": [{"name": "price", "type": "double"}, {"name": "quantity", "type": "double"}]
            }}},
            {"name": "offer", "type": {"type": "array", "items": "PriceLevel"}},
            {"name": "totalBidQtty", "type": "long"},
            {"name": "totalOfferQtty", "type": "long"},
            {"name": "source", "type": "string", "default": "DNSE"},
            {"name": "ingest_timestamp", "type": "long"}
        ]
    }),
    "expected_price": json.dumps({
        "type": "record", "name": "ExpectedPrice", "namespace": "com.vnstock.avro",
        "fields": [
            {"name": "symbol", "type": "string"},
            {"name": "marketId", "type": "string"},
            {"name": "boardId", "type": "string"},
            {"name": "closePrice", "type": "double"},
            {"name": "expectedTradePrice", "type": "double"},
            {"name": "expectedTradeQuantity", "type": "long"},
            {"name": "is_expected", "type": "boolean"},
            {"name": "source", "type": "string", "default": "DNSE"},
            {"name": "ingest_timestamp", "type": "long"}
        ]
    }),
    "security_def": json.dumps({
        "type": "record", "name": "SecurityDefinition", "namespace": "com.vnstock.avro",
        "fields": [
            {"name": "symbol", "type": "string"},
            {"name": "marketId", "type": "string"},
            {"name": "boardId", "type": "string"},
            {"name": "isin", "type": "string"},
            {"name": "basicPrice", "type": "double"},
            {"name": "ceilingPrice", "type": "double"},
            {"name": "floorPrice", "type": "double"},
            {"name": "securityStatus", "type": "string"},
            {"name": "source", "type": "string", "default": "DNSE"},
            {"name": "ingest_timestamp", "type": "long"}
        ]
    }),
}


def parse_args():
    p = argparse.ArgumentParser(description="VNStock Bronze: Kafka (Avro) → Iceberg")
    p.add_argument("--topic", required=True, help="Single Kafka topic")
    p.add_argument("--table", required=True, help="Target Iceberg table")
    p.add_argument("--checkpoint", required=True, help="S3 checkpoint directory")
    p.add_argument("--batch-size", type=int, default=5000)
    p.add_argument("--starting-offsets", default="earliest")
    return p.parse_args()


def main():
    args = parse_args()

    spark = SparkSession.builder \
        .appName(f"VNStock-Bronze-{args.topic}") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    kafka_bootstrap = spark.conf.get("spark.dataforge.kafka.bootstrap", "kafka:29092")
    avro_schema = AVRO_SCHEMAS.get(args.topic)
    if not avro_schema:
        raise ValueError(f"No Avro schema defined for topic: {args.topic}")

    spark.sql("CREATE DATABASE IF NOT EXISTS iceberg.bronze")

    # Read Avro-encoded messages from Kafka
    raw = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", kafka_bootstrap) \
        .option("subscribe", args.topic) \
        .option("startingOffsets", args.starting_offsets) \
        .option("maxOffsetsPerTrigger", args.batch_size) \
        .option("failOnDataLoss", "false") \
        .load()

    # Strip 5-byte Confluent wire format header, then parse Avro binary
    parsed = raw.select(
        col("topic"),
        col("timestamp").alias("kafka_timestamp"),
        from_avro(expr("substring(value, 6)"), avro_schema).alias("v")
    ).select("topic", "kafka_timestamp", "v.*") \
     .filter(col("symbol").isNotNull())

    # Write to Iceberg Bronze (AvailableNow = bounded streaming)
    query = parsed.writeStream \
        .format("iceberg") \
        .outputMode("append") \
        .option("checkpointLocation", args.checkpoint) \
        .trigger(availableNow=True) \
        .toTable(args.table)

    query.awaitTermination()
    logger.info("Bronze ingest complete: %s → %s", args.topic, args.table)
    spark.stop()


if __name__ == "__main__":
    main()

"""
Shared utilities for Spark ingestion jobs.

Contains:
  - build_spark(): creates an optimised SparkSession
  - decode_confluent_avro(): decodes Confluent Avro messages from Kafka
  - schema_id_expr(), payload_size_expr(): reusable Spark SQL Column expressions
  - ensure_schema(): creates a catalog schema if it does not yet exist
"""

from __future__ import annotations

import datetime
import decimal
import io
import json
import logging
from typing import Dict, Optional

from pyspark.sql import Column, SparkSession, functions as F

LOG = logging.getLogger(__name__)


# ============================================================
# === SPARK SESSION CONFIGURATION ===
# ============================================================
def build_spark(app_name: str) -> SparkSession:
    """
    Create or reuse a SparkSession with tuned memory and performance settings.

    Args:
        app_name: Spark application name shown in the Spark UI.

    Returns:
        SparkSession configured with adaptive execution, broadcast joins, and Arrow.

    Optimisations applied:
      - Adaptive Query Execution (AQE): auto-adjusts query plan at runtime
      - Coalesce Partitions: merges small partitions to reduce task overhead
      - Skew Join: handles skewed data transparently
      - Arrow Batching: speeds up PySpark Pandas conversions
    """
    builder = (SparkSession.builder
        .appName(app_name)
        # AQE: re-optimise plans based on actual runtime statistics
        .config("spark.sql.adaptive.enabled", "true")
        # Merge small post-shuffle partitions to reduce overhead
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        # Target partition size after coalescing (128 MB)
        .config("spark.sql.adaptive.advisoryPartitionSizeInBytes", "128MB")
        # Automatically split and replicate skewed join partitions
        .config("spark.sql.adaptive.skewJoin.enabled", "true")
        # Use Apache Arrow for fast JVM ⟷ Python data transfer
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        # Maximum rows per Arrow batch (memory cap)
        .config("spark.sql.execution.arrow.maxRecordsPerBatch", "10000")
        # Default partition count for shuffle operations
        .config("spark.sql.shuffle.partitions", "400")
        # Broadcast-join tables smaller than this threshold (avoids shuffle)
        .config("spark.sql.autoBroadcastJoinThreshold", "10MB")
    )

    return builder.getOrCreate()


# ============================================================
# === JSON SERIALIZATION HELPERS ===
# ============================================================
def _json_default(obj):
    """
    Custom JSON serializer for non-standard Python types.

    Used as the `default` callback in json.dumps() when the encoder encounters
    a type it cannot handle natively (datetime, Decimal, bytes).
    """
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()          # ISO 8601 string
    if isinstance(obj, decimal.Decimal):
        return str(obj)                 # keep full precision
    if isinstance(obj, (bytes, bytearray, memoryview)):
        return obj.hex()                # hex string for readability
    return str(obj)                     # fallback


# ============================================================
# === CONFLUENT AVRO DECODING ===
# ============================================================
def decode_confluent_avro(value: Optional[bytes], schema_registry_url: str) -> Optional[str]:
    """
    Decode a Confluent Avro binary payload into a JSON string.

    Confluent wire format:
      - Byte 0:    Magic byte (0x00)
      - Bytes 1-4: Schema ID (big-endian uint32)
      - Bytes 5+:  Avro binary-encoded record

    Args:
        value:               Raw bytes from the Kafka message value.
        schema_registry_url: Schema Registry URL (e.g. "http://schema-registry:8081").

    Returns:
        Compact JSON string representing the decoded record, or None if the
        payload is None, too short, or has an unexpected magic byte.

    Example:
        >>> payload = b'\\x00\\x00\\x00\\x01\\xaa\\xbb...'
        >>> json_str = decode_confluent_avro(payload, "http://localhost:8081")
    """
    # Reject None payloads or payloads shorter than the 5-byte header
    if value is None or len(value) < 5:
        return None
    # Check magic byte
    if value[0] != 0:
        return None

    # Extract schema ID from bytes 1-4 (big-endian unsigned int)
    schema_id = int.from_bytes(value[1:5], byteorder="big", signed=False)
    # Avro payload starts at byte 5
    payload = memoryview(value)[5:].tobytes()

    # Lazy imports to avoid hard dependencies when the function is not called
    from confluent_kafka.schema_registry import SchemaRegistryClient
    from fastavro import schemaless_reader

    client = SchemaRegistryClient({"url": schema_registry_url})
    schema_str = client.get_schema(schema_id).schema_str
    schema = json.loads(schema_str)
    record = schemaless_reader(io.BytesIO(payload), schema)
    return json.dumps(record, separators=(",", ":"), default=_json_default)


# ============================================================
# === SPARK SQL EXPRESSIONS ===
# ============================================================
def schema_id_expr(col: str) -> Column:
    """
    Return a Spark Column expression that extracts the Confluent Schema Registry ID
    from a binary Avro payload column.

    Args:
        col: Name of the DataFrame column containing raw Avro bytes.

    Returns:
        Integer Spark Column with the schema ID, or NULL if the payload is invalid.

    Example:
        >>> df.withColumn("schema_id", schema_id_expr("avro_payload"))
    """
    # Return NULL for null or too-short columns; otherwise decode bytes 1-4 as a hex int
    return F.when(
        (F.col(col).isNotNull()) & (F.length(col) >= 5),
        # hex() → substring bytes 2-5 (Spark uses 1-based indexing) → base-16 to base-10
        F.conv(F.hex(F.expr(f"substring({col}, 2, 4)")), 16, 10).cast("int"),
    ).otherwise(F.lit(None).cast("int"))


def payload_size_expr(col: str) -> Column:
    """
    Return a Spark Column expression for the Avro payload size in bytes,
    excluding the 5-byte Confluent wire-format header.

    Args:
        col: Name of the DataFrame column containing raw Avro bytes.

    Returns:
        Integer Spark Column with the payload byte count, or NULL if the column is null.

    Example:
        >>> df.withColumn("payload_bytes", payload_size_expr("avro_payload"))
    """
    # total length - 5-byte header (1 magic + 4 schema ID)
    return F.when(F.col(col).isNotNull(), F.length(col) - F.lit(5)).otherwise(F.lit(None))


# ============================================================
# === SCHEMA MANAGEMENT ===
# ============================================================
def ensure_schema(spark: SparkSession, schema_name: str) -> None:
    """
    Create the catalog schema if it does not already exist.

    Args:
        spark:       Active SparkSession.
        schema_name: Fully qualified schema name (e.g. 'iceberg.silver' or 'metastore.bronze').
    """
    try:
        schemas_df = spark.sql("SHOW SCHEMAS")
        existing_schemas = [row.databaseName for row in schemas_df.collect()]

        # Strip the catalog prefix to get the bare schema name (e.g. 'silver' from 'iceberg.silver')
        if "." in schema_name:
            _, schema_part = schema_name.split(".", 1)
        else:
            schema_part = schema_name

        if schema_part in existing_schemas:
            LOG.info("SCHEMA_EXISTS | schema=%s | status=confirmed", schema_name)
        else:
            spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            LOG.info("SCHEMA_CREATED | schema=%s | status=success", schema_name)
    except Exception:
        # Fallback: best-effort CREATE IF NOT EXISTS
        try:
            spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            LOG.info("SCHEMA_CREATED | schema=%s | status=success", schema_name)
        except Exception as create_error:
            LOG.warning("SCHEMA_CREATE_FAILED | schema=%s | error=%s", schema_name, str(create_error))


def ensure_iceberg_table(
    spark: SparkSession,
    table: str,
    columns_sql: str,
    *,
    partition_field: str = "event_source",
    table_properties: Optional[Dict[str, str]] = None,
) -> None:
    """Create the Iceberg table if it does not exist."""

    parts = table.split(".")
    if len(parts) != 3:
        raise ValueError("Table must be catalog.schema.table (e.g. iceberg.bronze.raw_events)")

    catalog, schema, _ = parts
    ensure_schema(spark, f"{catalog}.{schema}")

    properties = {"write.format.default": "parquet"}
    if table_properties:
        properties.update(table_properties)
    props_str = ", ".join(f"'{k}'='{v}'" for k, v in properties.items())

    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            {columns_sql}
        )
        USING iceberg
        PARTITIONED BY ({partition_field})
        TBLPROPERTIES ({props_str})
        """
    )
    LOG.info("TABLE_READY | table=%s | partition_by=%s | format=iceberg", table, partition_field)


def warn_if_checkpoint_exists(spark: SparkSession, checkpoint: str, *, logger: logging.Logger) -> None:
    """Warn when replay from earliest is requested but checkpoint already exists."""

    try:
        jvm = spark._jvm
        hconf = spark.sparkContext._jsc.hadoopConfiguration()
        path = jvm.org.apache.hadoop.fs.Path(checkpoint)
        fs = jvm.org.apache.hadoop.fs.FileSystem.get(path.toUri(), hconf)
        if fs.exists(path):
            logger.warning("CHECKPOINT_EXISTS | location=%s | starting_offsets=earliest | behavior=resume_from_checkpoint | " +
                          "note=use_new_checkpoint_path_to_replay_from_earliest", checkpoint)
    except Exception as exc:  # pragma: no cover - defensive
        logger.info("CHECKPOINT_CHECK_FAILED | location=%s | error=%s | behavior=continuing", checkpoint, str(exc))

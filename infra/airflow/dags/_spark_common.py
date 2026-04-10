from __future__ import annotations

import os
from typing import Iterable

from airflow.datasets import Dataset


# ===== SPARK PACKAGES & JARS CONFIGURATION =====
# Spark packages from Maven/Ivy repo (currently empty; add package coordinates here if needed)
_PACKAGES: list[str] = []

# Spark home directory — where the Spark runtime is installed inside the container
_SPARK_HOME = os.getenv("SPARK_HOME", "/opt/spark")

# Directory containing JAR dependency files
_JAR_DIR = os.getenv("SPARK_JARS_DIR", os.path.join(_SPARK_HOME, "jars"))

# Required JARs for every Spark job in this project.
# Includes: Kafka connector, Iceberg runtime, AWS/Hadoop libraries, Avro.
_EXTRA_JARS = [
    # Kafka Structured Streaming connector (Source/Sink for Spark)
    os.path.join(_JAR_DIR, "spark-sql-kafka-0-10_2.12-3.5.0.jar"),
    os.path.join(_JAR_DIR, "spark-token-provider-kafka-0-10_2.12-3.5.0.jar"),

    # Kafka Java client library (producer/consumer API)
    os.path.join(_JAR_DIR, "kafka-clients-3.5.0.jar"),

    # Apache Commons Pool2 — required by Kafka clients for connection pooling
    os.path.join(_JAR_DIR, "commons-pool2-2.12.0.jar"),

    # Iceberg runtime for Spark 3.5 — table format, MERGE INTO, schema evolution
    os.path.join(_JAR_DIR, "iceberg-spark-runtime-3.5_2.12-1.9.2.jar"),

    # Iceberg AWS bundle — S3FileIO, credential providers, request signing
    os.path.join(_JAR_DIR, "iceberg-aws-bundle-1.9.2.jar"),

    # Hadoop AWS connector — implements s3a:// FileSystem backed by MinIO/S3
    os.path.join(_JAR_DIR, "hadoop-aws-3.3.4.jar"),

    # AWS Java SDK bundle — provides S3, STS, and other AWS service clients
    os.path.join(_JAR_DIR, "aws-java-sdk-bundle-1.12.791.jar"),

    # Spark Avro — from_avro / to_avro functions for reading Confluent Avro from Kafka
    os.path.join(_JAR_DIR, "spark-avro_2.12-3.5.0.jar"),
]


# ===== BASE SPARK CONFIGURATION =====
# Core Spark configuration shared across all DAGs.
# Covers: Hive Metastore, resource allocation, Iceberg catalog, MinIO/S3, and Kafka.
_BASE_CONF = {
    # === HIVE METASTORE ===
    # Thrift endpoint for Hive Metastore (stores Iceberg table metadata/schema)
    "hive.metastore.uris": "thrift://hive-metastore:9083",
    "spark.hadoop.hive.metastore.uris": "thrift://hive-metastore:9083",

    # === SPARK CLUSTER ===
    # Spark standalone master — spark-master:7077 inside the Docker network
    "spark.master": "spark://spark-master:7077",

    # Deploy mode: 'client' means the driver runs inside the Airflow container so
    # Airflow can track job lifecycle and logs directly.
    "spark.submit.deployMode": "client",

    # === RESOURCE ALLOCATION ===
    # Number of executor JVM processes to launch (each gets its own CPU + memory)
    "spark.executor.instances": "2",

    # CPU cores per executor — controls how many tasks run in parallel per executor
    "spark.executor.cores": "1",

    # Heap memory per executor (used for caching, aggregation, shuffle buffers)
    "spark.executor.memory": "1G",

    # Fraction of executor memory reserved for data storage (caching) vs execution
    # 0.8 = 80% for cached data, 20% for execution buffers
    "spark.executor.memoryFraction": "0.8",

    # === ADAPTIVE QUERY EXECUTION ===
    # AQE re-optimizes query plans at runtime based on actual data statistics.
    # Handles data skew, coalesces small partitions, and selects optimal join strategies.
    "spark.sql.adaptive.enabled": "true",
    "spark.sql.adaptive.coalescePartitions.enabled": "true",

    # === WAREHOUSE ===
    # Root path for all Iceberg table data and metadata on S3/MinIO
    "spark.sql.warehouse.dir": "s3a://iceberg/warehouse",

    # === ICEBERG CATALOG ===
    # Adds Iceberg SQL extensions: CALL procedures, MERGE INTO, time-travel, etc.
    "spark.sql.extensions": "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",

    # Default catalog used when no catalog prefix is specified in SQL queries
    "spark.sql.defaultCatalog": "iceberg",

    # Make the built-in Spark catalog also Iceberg-aware (needed for CREATE TABLE AS SELECT)
    "spark.sql.catalog.spark_catalog": "org.apache.iceberg.spark.SparkSessionCatalog",

    # Register 'iceberg' as a custom Spark catalog backed by Hive Metastore via Thrift
    "spark.sql.catalog.iceberg": "org.apache.iceberg.spark.SparkCatalog",
    "spark.sql.catalog.iceberg.type": "hive",

    # Hive Metastore thrift endpoint — port 9083 is the binary Thrift protocol (not HTTP)
    "spark.sql.catalog.iceberg.uri": "thrift://hive-metastore:9083",

    # S3 path where Iceberg stores its table data and metadata JSON files
    "spark.sql.catalog.iceberg.warehouse": "s3a://iceberg/warehouse",

    # Use S3FileIO for direct S3-compatible object store I/O from Iceberg
    "spark.sql.catalog.iceberg.io-impl": "org.apache.iceberg.aws.s3.S3FileIO",

    # === S3 / MinIO ENDPOINT ===
    # MinIO S3-compatible API runs on port 9000 inside Docker (console is on 9001)
    "spark.sql.catalog.iceberg.s3.endpoint": "http://minio:9000",

    # Use path-style URLs (minio:9000/bucket/key) instead of virtual-hosted-style
    # (bucket.minio:9000/key) — required for MinIO and self-hosted S3-compatible stores
    "spark.sql.catalog.iceberg.s3.path-style-access": "true",
    
    # AWS region — required by the AWS SDK even though MinIO does not enforce it
    "spark.sql.catalog.iceberg.s3.region": "us-east-1",
    
    # === Hadoop FileSystem Configuration (S3A connector) ===
    # S3A endpoint pointing at the local MinIO service
    "spark.hadoop.fs.s3a.endpoint": "http://minio:9000",
    
    # Path-style access cho Hadoop S3A connector
    "spark.hadoop.fs.s3a.path.style.access": "true",
    
    # Disable SSL cho local MinIO (không có TLS certificate)
    "spark.hadoop.fs.s3a.connection.ssl.enabled": "false",
    
    # Credentials provider — SimpleAWSCredentialsProvider reads keys from config or env vars
    "spark.hadoop.fs.s3a.aws.credentials.provider": "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",

    # MinIO credentials in AWS access key format (MinIO uses the same auth model as S3)
    "spark.hadoop.fs.s3a.access.key": os.getenv("MINIO_ROOT_USER", "minio"),
    "spark.hadoop.fs.s3a.secret.key": os.getenv("MINIO_ROOT_PASSWORD", "minio123"),

    # S3A FileSystem implementation class for Hadoop
    "spark.hadoop.fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",

    # === KAFKA ===
    # Internal Docker network address for Kafka brokers (port 9092)
    # Spark Structured Streaming uses this to consume/produce messages
    "spark.dataforge.kafka.bootstrap": "kafka:9092",

    # Confluent Schema Registry — manages Avro schema versions for Kafka topics
    "spark.dataforge.schema.registry": "http://schema-registry:8081",

    # === JAR FILES ===
    # Comma-separated list of all extra JARs defined above.
    # Spark adds these to the driver and executor classpaths at submit time.
    "spark.jars": ",".join(_EXTRA_JARS),

    # === PERFORMANCE & STABILITY ===
    # Apache Arrow columnar memory format for JVM-to-Python data transfer.
    # Dramatically speeds up Pandas <-> Spark DataFrame conversions.
    "spark.sql.execution.arrow.pyspark.enabled": "true",

    # Detect and handle skewed join keys at runtime to prevent a single executor
    # from processing a disproportionately large amount of data.
    "spark.sql.adaptive.skewJoin.enabled": "true",

    # Maximum buffer size for Kryo serializer (faster than Java serialization).
    # 256 MB accommodates large broadcast variables and job state objects.
    "spark.kryoserializer.buffer.max": "256m",
}


def spark_packages() -> str | None:
    """
    Return the list of Spark packages (Maven coordinates) shared by all DAGs.

    Returns:
        str | None: Comma-separated Maven coordinates (e.g. "org.example:package:1.0.0"),
                    or None if no packages are configured.
    """
    return ",".join(_PACKAGES) if _PACKAGES else None


def spark_base_conf() -> dict[str, str]:
    """
    Return the baseline Spark configuration shared by all DAGs.

    Covers: Hive Metastore, cluster settings, resource allocation,
    Iceberg catalog, S3/MinIO endpoints, Kafka brokers, and Schema Registry.

    Returns:
        dict[str, str]: A shallow copy of _BASE_CONF (callers may mutate it safely).
    """
    return dict(_BASE_CONF)


def spark_env_vars() -> dict[str, str]:
    """
    Return environment variables required for Spark job submissions.

    Includes AWS-format credentials (MinIO mimics S3), region settings, and
    Spark installation paths. These are forwarded to Spark driver and executor processes.

    Returns:
        dict[str, str]: Environment variable map containing:
            - AWS_REGION / AWS_DEFAULT_REGION: us-east-1
            - AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY: MinIO root credentials
            - MINIO_ROOT_USER / MINIO_ROOT_PASSWORD: MinIO admin credentials
            - S3_ENDPOINT: MinIO API endpoint (http://minio:9000)
            - SPARK_HOME / SPARK_JARS_DIR: Spark installation paths
    """
    return {
        # AWS region setting — required by the AWS SDK even when using MinIO
        "AWS_REGION": os.getenv("AWS_REGION", "us-east-1"),
        "AWS_DEFAULT_REGION": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),

        # AWS-format credentials; MinIO uses the same access-key/secret-key model as S3
        "AWS_ACCESS_KEY_ID": os.getenv("MINIO_ROOT_USER", "minio"),
        "AWS_SECRET_ACCESS_KEY": os.getenv("MINIO_ROOT_PASSWORD", "minio123"),

        # MinIO admin credentials (for direct MinIO API calls if needed)
        "MINIO_ROOT_USER": os.getenv("MINIO_ROOT_USER", "minio"),
        "MINIO_ROOT_PASSWORD": os.getenv("MINIO_ROOT_PASSWORD", "minio123"),

        # S3-compatible endpoint where Spark sends object storage requests
        "S3_ENDPOINT": os.getenv("S3_ENDPOINT", os.getenv("MINIO_ENDPOINT", "minio:9000")),

        # Spark runtime installation path inside the container
        "SPARK_HOME": os.getenv("SPARK_HOME", "/opt/spark"),

        # Directory where Spark searches for extra JAR files
        "SPARK_JARS_DIR": os.getenv("SPARK_JARS_DIR", "/opt/spark/jars"),
    }


def spark_job_base() -> str:
    """
    Return the base path where Spark job files are mounted inside the container.

    Usually /opt/spark/jobs — the directory holding all Python/Scala job scripts.

    Returns:
        str: Absolute path (default: /opt/spark/jobs).
    """
    return os.getenv("SPARK_JOB_BASE", "/opt/spark/jobs")


def spark_utils_py_files() -> str:
    """
    Return comma-separated py_files that are distributed alongside every Spark job.

    py_files are Python modules shipped to Spark executors so they can be imported
    inside UDFs and job code. Typically contains shared utilities like spark_utils.py.

    Returns:
        str: Comma-separated file paths compatible with spark-submit --py-files
             (e.g. "/opt/spark/jobs/spark_utils.py").
    """
    # Build path to spark_utils.py inside the job base directory
    utils_path = os.getenv("SPARK_UTILS_PATH", os.path.join(spark_job_base(), "spark_utils.py"))
    return ",".join([utils_path])


def iceberg_dataset(table: str) -> Dataset:
    """
    Convert an Iceberg table name (catalog.schema.table) into an Airflow Dataset URI.

    Airflow uses Dataset URIs to track data lineage between upstream producers
    and downstream consumers across DAGs.

    Args:
        table (str): Fully qualified table name in "catalog.schema.table" format
                     (e.g. "iceberg.silver.fact_orders").

    Returns:
        Dataset: Airflow Dataset pointing to the S3 path of the Iceberg table
                 (e.g. Dataset("s3://iceberg/warehouse/silver.db/fact_orders/")).

    Raises:
        ValueError: If the table string does not contain exactly three dot-separated parts.
    """
    catalog, schema, tbl = table.split(".")
    # Iceberg stores table data and metadata under: s3://warehouse/{schema}.db/{table}/
    return Dataset(f"s3://iceberg/warehouse/{schema}.db/{tbl}/")


def iceberg_maintenance(table: str, expire_days: str = "7d") -> None:
    """
    Run Iceberg maintenance operations on the specified table.

    Iceberg stores every write as a new immutable snapshot, so periodic
    maintenance is needed to prevent unbounded growth of metadata and storage.
    Three operations are performed:
      - OPTIMIZE: Rewrites many small Parquet files into fewer larger ones,
        improving query scan performance.
      - EXPIRE_SNAPSHOTS: Deletes snapshots older than `expire_days`, freeing
        the metadata and data files they reference.
      - REMOVE_ORPHAN_FILES: Deletes S3 objects not referenced by any snapshot
        (can accumulate after partial write failures).

    Args:
        table (str): Fully qualified table name in "catalog.schema.table" format.
        expire_days (str): Snapshot retention window (e.g. "7d", "30d").

    Raises:
        ValueError: If the table string does not have three dot-separated parts.
        trino.exceptions.TrinoError: If the Trino connection or query fails.
    """
    import trino

    parts = table.split(".")
    if len(parts) != 3:
        raise ValueError(f"Expected table as catalog.schema.table, got: {table}")
    catalog, schema, tbl = parts

    # Connect to Trino SQL engine (port 8080) to run Iceberg DDL/procedure calls
    conn = trino.dbapi.connect(host="trino", port=8080, user="airflow")
    cur = conn.cursor()
    fqtn = f"{catalog}.{schema}.{tbl}"

    # Compact small files → fewer large files; updates table statistics
    cur.execute(f"ALTER TABLE {fqtn} EXECUTE optimize")
    _ = cur.fetchall()

    # Remove snapshots older than the retention threshold
    cur.execute(
        f"ALTER TABLE {fqtn} EXECUTE expire_snapshots(retention_threshold => '{expire_days}')"
    )
    _ = cur.fetchall()

    # Delete unreferenced S3 objects left over from failed or partial writes
    cur.execute(f"ALTER TABLE {fqtn} EXECUTE remove_orphan_files")
    _ = cur.fetchall()


def maintenance_tasks_for(dag, upstream_task, tables: Iterable[str], expire_days: str = "7d") -> None:
    """
    Create Iceberg maintenance PythonOperator tasks, one per table.

    For each table, a PythonOperator is created that calls iceberg_maintenance().
    All maintenance tasks are chained after `upstream_task`.

    Args:
        dag: The Airflow DAG object that owns the tasks.
        upstream_task: The task that must complete before any maintenance runs.
        tables (Iterable[str]): Table names in "catalog.schema.table" format.
        expire_days (str): Snapshot retention threshold for EXPIRE_SNAPSHOTS (e.g. "7d").

    Side Effects:
        - Adds new PythonOperator tasks to `dag`.
        - Registers upstream_task >> maintenance_task dependencies.
    """
    from airflow.providers.standard.operators.python import PythonOperator

    for table in tables:
        maintenance = PythonOperator(
            task_id=f"iceberg_maintenance_{table.split('.')[-1]}",
            python_callable=iceberg_maintenance,
            op_kwargs={"table": table, "expire_days": expire_days},
        )
        upstream_task >> maintenance

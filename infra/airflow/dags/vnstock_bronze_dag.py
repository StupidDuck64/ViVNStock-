"""
VNStock Bronze Streaming DAG

Runs the VNStock Spark Structured Streaming job that consumes Confluent Avro
messages from the 'vnstock.ohlc.realtime' Kafka topic produced by the DNSE
producer (producer.py / producer_ws.py) and writes micro-batches into
Iceberg Bronze + Redis.

Topic → Table:
  vnstock.ohlc.realtime (Confluent Avro) → iceberg.bronze.vnstock_ohlc_1m
                                          → Redis vnstock:tick:{SYMBOL}

The streaming job runs continuously. This DAG triggers it via SparkSubmitOperator
with 'AvailableNow' semantics (Airflow kills the app once no new offsets remain).
For true continuous streaming, run the job outside Airflow (e.g., supervisord).

Maintenance task OPTIMIZE + EXPIRE_SNAPSHOTS runs after each triggered batch.
"""

import os

from airflow import DAG
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.providers.standard.operators.python import PythonOperator

from _spark_common import (
    iceberg_dataset,
    iceberg_maintenance,
    spark_base_conf,
    spark_env_vars,
    spark_job_base,
    spark_packages,
    spark_utils_py_files,
)

default_args = {"owner": "VNStock", "depends_on_past": False, "retries": 1}

PACKAGES = spark_packages()
BASE_CONF = spark_base_conf()
ENV_VARS = {
    **spark_env_vars(),
    "KAFKA_TOPIC": "vnstock.ohlc.realtime",
    "SCHEMA_REGISTRY_URL": os.getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081"),
}
SPARK_JOB_BASE = spark_job_base()
SPARK_PY_FILES = spark_utils_py_files()

# streaming.py is the actual Spark streaming job
APPLICATION = os.path.join(SPARK_JOB_BASE, "vnstock", "streaming.py")

with DAG(
    dag_id="vnstock_bronze_streaming",
    description="VNStock Kafka → Iceberg Bronze streaming (Confluent Avro, vnstock.ohlc.realtime)",
    doc_md="""\
#### VNStock Bronze Streaming

**Purpose**: Consume `vnstock.ohlc.realtime` Kafka topic (Confluent Avro format)
and write micro-batches into `iceberg.bronze.vnstock_ohlc_1m` + Redis.

**Pipeline**:
1. Producer (DNSE REST or WebSocket) → Kafka `vnstock.ohlc.realtime`
2. Avro deserialization via Schema Registry UDF
3. Deduplication by (symbol, time)
4. Append to Iceberg `bronze.vnstock_ohlc_1m`
5. Write latest tick per symbol to Redis `vnstock:tick:{SYMBOL}`
    """,
    start_date=None,
    schedule=None,
    catchup=False,
    max_active_tasks=2,
    default_args=default_args,
    tags=["vnstock", "bronze", "streaming"],
) as dag:

    ingest = SparkSubmitOperator(
        task_id="stream_ohlc_realtime",
        conn_id="spark_default",
        application=APPLICATION,
        py_files=SPARK_PY_FILES,
        packages=PACKAGES,
        env_vars=ENV_VARS,
        conf=BASE_CONF,
        verbose=True,
        outlets=[iceberg_dataset("iceberg.bronze.vnstock_ohlc_1m")],
    )

    maintenance = PythonOperator(
        task_id="maintenance_ohlc_1m",
        python_callable=iceberg_maintenance,
        op_kwargs={"table": "iceberg.bronze.vnstock_ohlc_1m", "expire_days": "7d"},
    )

    ingest >> maintenance

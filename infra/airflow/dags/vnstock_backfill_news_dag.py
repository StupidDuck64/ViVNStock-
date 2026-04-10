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
ENV_VARS = spark_env_vars()
SPARK_JOB_BASE = spark_job_base()
SPARK_PY_FILES = spark_utils_py_files()


# ── DAG 1: Daily Backfill (runs at 16:00 on weekdays, after market close) ──
with DAG(
    dag_id="vnstock_backfill_daily",
    description="Daily historical data backfill via vnstock3",
    doc_md="""\
#### VNStock Daily Backfill

Uses vnstock3 library (TCBS source) to download daily historical OHLCV data.
Runs after market close (16:00).

**Output**: `iceberg.gold.vnstock_ohlc_1d`
    """,
    start_date=None,
    schedule="0 16 * * 1-5",
    catchup=False,
    default_args=default_args,
    tags=["vnstock", "backfill"],
) as backfill_dag:

    backfill_1d = SparkSubmitOperator(
        task_id="backfill_daily",
        conn_id="spark_default",
        application=os.path.join(SPARK_JOB_BASE, "vnstock", "vnstock_backfill_1d.py"),
        py_files=SPARK_PY_FILES,
        packages=PACKAGES,
        env_vars=ENV_VARS,
        conf=BASE_CONF,
        verbose=True,
        outlets=[iceberg_dataset("iceberg.gold.vnstock_ohlc_1d")],
    )

    maintenance = PythonOperator(
        task_id="maintenance_ohlc_1d",
        python_callable=iceberg_maintenance,
        op_kwargs={"table": "iceberg.gold.vnstock_ohlc_1d", "expire_days": "30d"},
    )

    backfill_1d >> maintenance


# ── DAG 2: 1-Minute Backfill (manual trigger only) ─────────────
with DAG(
    dag_id="vnstock_backfill_1m",
    description="1-minute OHLC backfill (vnstock3 primary, DNSE backup) + aggregation",
    doc_md="""\
#### VNStock 1-Minute Backfill

Primary: vnstock3 (VCI source, no request limit).
Backup: DNSE REST API (100 req/h, 1000 req/day, 36s delay).

After loading 1m data, automatically aggregates to 5m, 15m, 30m, 1h, 4h.
Retention: 90 days. Triggered manually from Airflow UI.

**Output**: `iceberg.bronze.vnstock_ohlc_1m` + 5 aggregated tables
    """,
    start_date=None,
    schedule=None,
    catchup=False,
    default_args=default_args,
    params={"symbols": "VCB,HPG,FPT,VIC,VHM", "delay": 36, "days": 90},
    tags=["vnstock", "backfill", "manual"],
) as backfill_1m_dag:

    backfill_1m = SparkSubmitOperator(
        task_id="backfill_1m",
        conn_id="spark_default",
        application=os.path.join(SPARK_JOB_BASE, "vnstock", "vnstock_backfill_1m.py"),
        py_files=SPARK_PY_FILES,
        packages=PACKAGES,
        env_vars=ENV_VARS,
        conf=BASE_CONF,
        application_args=[
            "--symbols", "{{ params.symbols }}",
            "--delay", "{{ params.delay }}",
            "--days", "{{ params.days }}",
        ],
        verbose=True,
        outlets=[iceberg_dataset("iceberg.bronze.vnstock_ohlc_1m")],
    )


# ── DAG 3: News Crawler (every 30 minutes during market hours) ──
with DAG(
    dag_id="vnstock_news_crawler",
    description="Crawl financial news from CafeF, Vietstock, VnEconomy",
    doc_md="""\
#### VNStock News Crawler

Scrapes stock market news from CafeF, Vietstock, VnEconomy.
Stores in Redis for real-time API serving.

**Redis keys**: `vnstock:news:all`, `vnstock:news:{source}`
    """,
    start_date=None,
    schedule="*/30 8-16 * * 1-5",
    catchup=False,
    default_args=default_args,
    tags=["vnstock", "news"],
) as news_dag:

    crawl = SparkSubmitOperator(
        task_id="crawl_news",
        conn_id="spark_default",
        application=os.path.join(SPARK_JOB_BASE, "vnstock", "vnstock_news_crawler.py"),
        py_files=SPARK_PY_FILES,
        packages=PACKAGES,
        env_vars=ENV_VARS,
        conf=BASE_CONF,
        verbose=True,
    )


# ── DAG 4: Bronze → Silver Compaction ──────────────────────────
COMPACT_PAIRS = {
    "ohlc_stock":      ("iceberg.bronze.vnstock_ohlc_stock",      "iceberg.silver.vnstock_ohlc_stock"),
    "ohlc_derivative": ("iceberg.bronze.vnstock_ohlc_derivative", "iceberg.silver.vnstock_ohlc_derivative"),
    "ohlc_index":      ("iceberg.bronze.vnstock_ohlc_index",      "iceberg.silver.vnstock_ohlc_index"),
    "quote":           ("iceberg.bronze.vnstock_quote",            "iceberg.silver.vnstock_quote"),
    "expected_price":  ("iceberg.bronze.vnstock_expected_price",   "iceberg.silver.vnstock_expected_price"),
    "security_def":    ("iceberg.bronze.vnstock_security_def",     "iceberg.silver.vnstock_security_def"),
}

with DAG(
    dag_id="vnstock_compact_bronze_to_silver",
    description="Compact Bronze → Silver (dedup + repartition by symbol)",
    doc_md="""\
#### VNStock Bronze → Silver Compaction

Reads Bronze tables, deduplicates by (symbol, time), repartitions by symbol,
writes to Silver Iceberg. Each file in Silver contains data for exactly one stock symbol.

Runs daily after Bronze ingestion completes (17:00).
    """,
    start_date=None,
    schedule="0 17 * * 1-5",
    catchup=False,
    max_active_tasks=3,
    default_args=default_args,
    tags=["vnstock", "compact", "silver"],
) as compact_dag:

    for key, (bronze, silver) in COMPACT_PAIRS.items():
        compact_task = SparkSubmitOperator(
            task_id=f"compact_{key}",
            conn_id="spark_default",
            application=os.path.join(SPARK_JOB_BASE, "vnstock", "vnstock_compact.py"),
            py_files=SPARK_PY_FILES,
            packages=PACKAGES,
            env_vars=ENV_VARS,
            conf=BASE_CONF,
            application_args=[
                "--bronze-table", bronze,
                "--silver-table", silver,
            ],
            verbose=True,
            outlets=[iceberg_dataset(silver)],
        )

        silver_maintenance = PythonOperator(
            task_id=f"maintenance_silver_{key}",
            python_callable=iceberg_maintenance,
            op_kwargs={"table": silver, "expire_days": "14d"},
        )

        compact_task >> silver_maintenance

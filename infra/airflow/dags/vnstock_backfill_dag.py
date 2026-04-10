from __future__ import annotations

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

# ─── Helper: collect all symbols into one comma-separated string ─
def _all_symbols_str() -> str:
    """Merge per-board symbol env vars into a single comma-separated string."""
    boards = [
        "VNSTOCK_SYMBOLS_HOSE",
        "VNSTOCK_SYMBOLS_HNX",
        "VNSTOCK_SYMBOLS_UPCOM",
        "VNSTOCK_SYMBOLS_DERIVATIVE",
        "VNSTOCK_SYMBOLS_INDEX",
    ]
    parts = []
    for var in boards:
        raw = os.getenv(var, "")
        if raw:
            parts.append(raw.strip().strip(","))
    # Fallback to combined VNSTOCK_SYMBOLS if per-board vars not set
    if not parts:
        return os.getenv("VNSTOCK_SYMBOLS", "VCB,HPG,FPT")
    return ",".join(parts)


def _check_api_key(**_):
    """Fail-fast check: abort immediately if DNSE_API_KEY is not set."""
    api_key = os.getenv("DNSE_API_KEY", "")
    if not api_key:
        raise ValueError(
            "DNSE_API_KEY is not set. "
            "Add it to .env and make sure it is passed to the Airflow container."
        )


# ─── Shared Spark configuration ──────────────────────────────────
PACKAGES = spark_packages()
BASE_CONF = spark_base_conf()
ENV_VARS = {
    **spark_env_vars(),
    "DNSE_API_KEY": os.getenv("DNSE_API_KEY", ""),
}
SPARK_JOB_BASE = spark_job_base()
SPARK_PY_FILES = spark_utils_py_files()

# Override driver memory for long-running backfill jobs.
# Both jobs use 1 executor core to leave headroom for streaming/serving.
BACKFILL_CONF = {
    **BASE_CONF,
    "spark.driver.memory": "2G",
    "spark.executor.memory": "2G",
    "spark.executor.instances": "1",
    "spark.executor.cores": "1",
}

ALL_SYMBOLS = _all_symbols_str()

default_args = {
    "owner": "VNStock",
    "depends_on_past": False,
    "retries": 1,
}

# ════════════════════════════════════════════════════════════════
# DAG 1: Daily backfill_1m + aggregations  (runs every day 01:00)
# ════════════════════════════════════════════════════════════════
with DAG(
    dag_id="vnstock_backfill_1m_daily",
    description="Daily incremental 1m OHLCV + aggregations (high-water mark) for all symbols",
    doc_md="""\
#### VNStock 1-Minute Backfill (Daily Incremental)

Fetches **new 1-minute candles** for all ~1 012 symbols since the last
successful run using a high-water mark (MAX(time) per symbol in Iceberg).

Higher-resolution aggregations (5m, 15m, 30m, 1h, 4h) are recomputed
from the full 1m table after the append.

**Primary source**: VCI (`vnstock` library, ~2.5 years of history)  
**Fallback source**: DNSE REST API (~90 days)  
**Target tables**: `iceberg.bronze.vnstock_ohlc_1m / 5m / 15m / 30m / 1h / 4h`  
**Run mode**: `--run-mode daily` — append only, safe for scheduled execution  
    """,
    schedule="0 18 * * *",   # 01:00 ICT = 18:00 UTC
    start_date=None,
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["vnstock", "backfill", "bronze", "1m"],
) as dag_1m:

    check_key_1m = PythonOperator(
        task_id="check_api_key",
        python_callable=_check_api_key,
    )

    run_backfill_1m = SparkSubmitOperator(
        task_id="backfill_1m",
        conn_id="spark_default",
        application=os.path.join(SPARK_JOB_BASE, "vnstock", "backfill_1m.py"),
        py_files=SPARK_PY_FILES,
        packages=PACKAGES,
        env_vars=ENV_VARS,
        conf=BACKFILL_CONF,
        application_args=[
            "--symbols", ALL_SYMBOLS,
            "--days", "3",
            "--run-mode", "daily",
            "--batch-size", "50",
        ],
        verbose=True,
        outlets=[
            iceberg_dataset("iceberg.bronze.vnstock_ohlc_1m"),
        ],
    )

    maintenance_1m = PythonOperator(
        task_id="maintenance_1m",
        python_callable=iceberg_maintenance,
        op_kwargs={"table": "iceberg.bronze.vnstock_ohlc_1m", "expire_days": "30d"},
    )

    check_key_1m >> run_backfill_1m >> maintenance_1m


# ════════════════════════════════════════════════════════════════
# DAG 2: Daily incremental backfill_1d  (runs every day 02:00)
# ════════════════════════════════════════════════════════════════
with DAG(
    dag_id="vnstock_backfill_1d_weekly",
    description="Daily incremental daily-bar backfill (high-water mark) for all symbols",
    doc_md="""\
#### VNStock Daily Backfill (Incremental)

Fetches **new daily candles** for all ~1 012 symbols since the last
successful run using a high-water mark (MAX(time) per symbol in Iceberg).

**Source**: DNSE REST API (resolution=1D)  
**Target table**: `iceberg.bronze.vnstock_ohlc_1d`  
**Run mode**: `--run-mode daily` — append only, safe for scheduled execution  
    """,
    schedule="0 19 * * *",  # 02:00 ICT = 19:00 UTC (daily instead of weekly)
    start_date=None,
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["vnstock", "backfill", "bronze", "1d"],
) as dag_1d:

    check_key_1d = PythonOperator(
        task_id="check_api_key",
        python_callable=_check_api_key,
    )

    run_backfill_1d = SparkSubmitOperator(
        task_id="backfill_1d",
        conn_id="spark_default",
        application=os.path.join(SPARK_JOB_BASE, "vnstock", "backfill_1d.py"),
        py_files=SPARK_PY_FILES,
        packages=PACKAGES,
        env_vars=ENV_VARS,
        conf=BACKFILL_CONF,
        application_args=[
            "--symbols", ALL_SYMBOLS,
            "--start-date", "2015-01-01",
            "--run-mode", "daily",
            "--batch-size", "100",
        ],
        verbose=True,
        outlets=[
            iceberg_dataset("iceberg.bronze.vnstock_ohlc_1d"),
        ],
    )

    maintenance_1d = PythonOperator(
        task_id="maintenance_1d",
        python_callable=iceberg_maintenance,
        op_kwargs={"table": "iceberg.bronze.vnstock_ohlc_1d", "expire_days": "30d"},
    )

    check_key_1d >> run_backfill_1d >> maintenance_1d

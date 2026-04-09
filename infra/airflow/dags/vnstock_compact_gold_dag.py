"""
VNStock Compact & Gold DAG

Orchestrates Spark jobs for:
  1. Bronze compaction — dedup + repartition by symbol per timeframe
  2. Gold daily summary — prev_close, change_pct, sector mapping

Schedule: Daily 03:00 ICT (after backfill DAGs complete at 01:00 + 02:00)

DAG design:
  ┌──────────────────────────────────────────────────────┐
  │ compact_1m  (SparkSubmitOperator)                    │
  │   bronze.vnstock_ohlc_1m → silver.vnstock_ohlc_1m   │
  └──────────┬───────────────────────────────────────────┘
             │  (parallel with compact_1d)
  ┌──────────▼───────────────────────────────────────────┐
  │ compact_1d  (SparkSubmitOperator)                    │
  │   bronze.vnstock_ohlc_1d → silver.vnstock_ohlc_1d   │
  └──────────┬───────────────────────────────────────────┘
             │
  ┌──────────▼───────────────────────────────────────────┐
  │ gold_daily_summary  (SparkSubmitOperator)            │
  │   bronze.vnstock_ohlc_1d → gold.vnstock_daily_summary│
  └──────────┬───────────────────────────────────────────┘
             │
  ┌──────────▼───────────────────────────────────────────┐
  │ maintenance  (PythonOperator)                        │
  │   OPTIMIZE + EXPIRE_SNAPSHOTS on all tables          │
  └──────────────────────────────────────────────────────┘
"""

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

# ─── Shared configuration ──
PACKAGES = spark_packages()
BASE_CONF = spark_base_conf()
ENV_VARS = spark_env_vars()
SPARK_JOB_BASE = spark_job_base()
SPARK_PY_FILES = spark_utils_py_files()

COMPACT_CONF = {
    **BASE_CONF,
    "spark.driver.memory": "2G",
    "spark.executor.memory": "2G",
    "spark.executor.instances": "2",
    "spark.executor.cores": "1",
}

GOLD_CONF = {
    **BASE_CONF,
    "spark.driver.memory": "1G",
    "spark.executor.memory": "1G",
    "spark.executor.instances": "1",
    "spark.executor.cores": "1",
}

# ─── Tables to compact (bronze → silver) ──
COMPACT_PAIRS = [
    ("iceberg.bronze.vnstock_ohlc_1m", "iceberg.silver.vnstock_ohlc_1m"),
    ("iceberg.bronze.vnstock_ohlc_5m", "iceberg.silver.vnstock_ohlc_5m"),
    ("iceberg.bronze.vnstock_ohlc_15m", "iceberg.silver.vnstock_ohlc_15m"),
    ("iceberg.bronze.vnstock_ohlc_30m", "iceberg.silver.vnstock_ohlc_30m"),
    ("iceberg.bronze.vnstock_ohlc_1h", "iceberg.silver.vnstock_ohlc_1h"),
    ("iceberg.bronze.vnstock_ohlc_4h", "iceberg.silver.vnstock_ohlc_4h"),
    ("iceberg.bronze.vnstock_ohlc_1d", "iceberg.silver.vnstock_ohlc_1d"),
]

# All tables needing maintenance
MAINTENANCE_TABLES = [silver for _, silver in COMPACT_PAIRS] + [
    "iceberg.gold.vnstock_daily_summary",
]

default_args = {
    "owner": "VNStock",
    "depends_on_past": False,
    "retries": 1,
}


def _run_all_maintenance(**_):
    """Run Iceberg maintenance on all silver + gold tables."""
    for table in MAINTENANCE_TABLES:
        try:
            iceberg_maintenance(table, expire_days="30d")
        except Exception as e:
            # Log but don't fail — table might not exist yet
            import logging
            logging.getLogger("compact_gold_dag").warning(
                "Maintenance skipped for %s: %s", table, e
            )


with DAG(
    dag_id="vnstock_compact_gold_daily",
    description="Daily: compact bronze → silver; build gold daily summary (Spark)",
    doc_md="""\
#### VNStock Compact & Gold Pipeline

**Schedule**: Daily 03:00 ICT (after backfill DAGs)

**Step 1 — Compact** (parallel):
Deduplicates and repartitions each bronze OHLCV table by symbol,
writing cleaner, larger files into silver. 1 Parquet file = 1 symbol.

**Step 2 — Gold Daily Summary**:
Reads daily OHLCV from bronze, computes:
- `prev_close` (LAG window by symbol)
- `change` = close − prev_close
- `change_pct` = (close − prev_close) / prev_close × 100
- `sector` mapping (Vietnamese ICB-based classification)

Target: `iceberg.gold.vnstock_daily_summary` (partitioned by trade_date).
Feeds PriceBoard Top Movers and SectorHeatmap.

**Step 3 — Maintenance**:
OPTIMIZE + EXPIRE_SNAPSHOTS on all silver + gold tables.
    """,
    schedule="0 20 * * *",   # 03:00 ICT = 20:00 UTC
    start_date=None,
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["vnstock", "compact", "silver", "gold"],
) as dag:

    # ── Step 1: Compact bronze → silver (all timeframes) ──
    compact_tasks = []
    for bronze_table, silver_table in COMPACT_PAIRS:
        tf = bronze_table.split("_")[-1]  # 1m, 5m, 15m, ...
        task = SparkSubmitOperator(
            task_id=f"compact_{tf}",
            conn_id="spark_default",
            application=os.path.join(SPARK_JOB_BASE, "vnstock", "compact.py"),
            py_files=SPARK_PY_FILES,
            packages=PACKAGES,
            env_vars=ENV_VARS,
            conf=COMPACT_CONF,
            application_args=[
                "--bronze-table", bronze_table,
                "--silver-table", silver_table,
            ],
            verbose=True,
            outlets=[iceberg_dataset(silver_table)],
        )
        compact_tasks.append(task)

    # ── Step 2: Gold daily summary ──
    gold_summary = SparkSubmitOperator(
        task_id="gold_daily_summary",
        conn_id="spark_default",
        application=os.path.join(SPARK_JOB_BASE, "vnstock", "gold_daily_summary.py"),
        py_files=SPARK_PY_FILES,
        packages=PACKAGES,
        env_vars=ENV_VARS,
        conf=GOLD_CONF,
        application_args=[
            "--source-table", "iceberg.bronze.vnstock_ohlc_1d",
            "--target-table", "iceberg.gold.vnstock_daily_summary",
            "--mode", "full",
        ],
        verbose=True,
        outlets=[iceberg_dataset("iceberg.gold.vnstock_daily_summary")],
    )

    # ── Step 3: Maintenance ──
    maintenance = PythonOperator(
        task_id="iceberg_maintenance_all",
        python_callable=_run_all_maintenance,
    )

    # ── DAG wiring: compact ──(all parallel)──> gold_summary ──> maintenance ──
    for t in compact_tasks:
        t >> gold_summary
    gold_summary >> maintenance

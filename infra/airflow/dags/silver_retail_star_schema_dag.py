"""
Airflow DAG for building the Silver layer — Kimball Star Schema.

Defines Airflow tasks that construct the star schema (Kimball dimensional model)
from Bronze-layer data. Covers dimension tables (Customer, Product, Supplier,
Warehouse, Date) and fact tables (Order Service, Inventory Position, Customer Engagement).

Workflow:
  1. Load the Date dimension first (no upstream dependencies)
  2. Load all other dimension tables in parallel (Customer, Product, Supplier, Warehouse)
  3. Load fact tables last (depend on all dimensions being ready)
  4. Run Iceberg maintenance after each table (OPTIMIZE, EXPIRE_SNAPSHOTS, REMOVE_ORPHANS)

Trigger: DAG fires automatically whenever any upstream Bronze dataset is updated.
"""

import os
from typing import Dict

from airflow import DAG
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator

from _spark_common import (
    iceberg_dataset,
    iceberg_maintenance,
    spark_base_conf,
    spark_env_vars,
    spark_job_base,
    spark_packages,
    spark_utils_py_files,
)
from silver import TABLE_BUILDERS, TableBuilder


# ===== DEFAULT AIRFLOW SETTINGS =====
# Baseline config applied to all tasks in this DAG
default_args = {"owner": "DataForge", "depends_on_past": False, "retries": 1}


# ===== SPARK CONFIGURATION =====
# Loaded from _spark_common: Maven packages, base Spark conf (Hive/Iceberg/S3/Kafka),
# and environment variables (AWS credentials, paths).
PACKAGES = spark_packages()
BASE_CONF = spark_base_conf()
ENV_VARS = spark_env_vars()

# Base path where Spark job files are mounted inside the container
SPARK_JOB_BASE = spark_job_base()

# Path to the Python driver script that builds Silver tables
SILVER_APPLICATION = os.path.join(SPARK_JOB_BASE, "silver_retail_service.py")

# Python files distributed to Spark executors (e.g. spark_utils.py)
SPARK_PY_FILES = spark_utils_py_files()


# ===== SILVER TABLE CONFIGURATION =====
# Map from short identifier to fully qualified table name
# e.g. "dim_customer_profile" → "iceberg.silver.dim_customer_profile"
SILVER_TABLES = {builder.identifier: builder.table for builder in TABLE_BUILDERS}


# ===== DATASET TRIGGERS =====
# Airflow Dataset URIs that this DAG listens to.
# Any update to a Bronze dataset automatically schedules a new DAG run.
TRIGGER_DATASETS = [
    iceberg_dataset("iceberg.bronze.raw_events"),
    iceberg_dataset("iceberg.bronze.demo_public_users"),
    iceberg_dataset("iceberg.bronze.demo_public_products"),
    iceberg_dataset("iceberg.bronze.demo_public_inventory"),
    iceberg_dataset("iceberg.bronze.demo_public_suppliers"),
    iceberg_dataset("iceberg.bronze.demo_public_customer_segments"),
    iceberg_dataset("iceberg.bronze.demo_public_warehouse_inventory"),
]


# ===== DAG CONFIGURATION =====
DEFAULT_CONFIG = {
    # Iceberg snapshot retention window (snapshots older than 14 days are expired)
    "expire_days": "14d",
    # Maximum tasks running in parallel per DAG run (protects the Spark cluster)
    "max_active_tasks": 2,
}


# ===== FACTORY FUNCTION =====
def create_silver_task(builder: TableBuilder, dag) -> tuple[SparkSubmitOperator, object]:
    """
    Factory that creates a (build_task, maintenance_task) pair for one Silver table.

    The build task runs spark-submit to materialise the table.
    The maintenance task then runs Iceberg OPTIMIZE / EXPIRE_SNAPSHOTS / REMOVE_ORPHAN_FILES.

    Args:
        builder: TableBuilder config from silver.registry (identifier, table name, etc.)
        dag:     Airflow DAG instance that owns the tasks.

    Returns:
        (SparkSubmitOperator, PythonOperator): build_task, maintenance_task
    """
    # Submit silver_retail_service.py via spark-submit
    build_task = SparkSubmitOperator(
        task_id=f"build_{builder.identifier}",
        conn_id="spark_default",
        application=SILVER_APPLICATION,
        py_files=SPARK_PY_FILES,
        packages=PACKAGES,
        env_vars=ENV_VARS,
        conf=BASE_CONF,
        application_args=["--tables", builder.identifier],
        verbose=True,
        # Mark this Iceberg table as produced by the task for Airflow lineage tracking
        outlets=[iceberg_dataset(builder.table)],
        dag=dag,
    )

    from airflow.providers.standard.operators.python import PythonOperator

    maintenance_task = PythonOperator(
        task_id=f"iceberg_maintenance_{builder.identifier}",
        python_callable=iceberg_maintenance,
        op_kwargs={
            "table": builder.table,
            "expire_days": DEFAULT_CONFIG["expire_days"],
        },
        dag=dag,
    )

    # Maintenance runs after the build is complete
    build_task >> maintenance_task

    return build_task, maintenance_task


# ===== AIRFLOW DAG DEFINITION =====
with DAG(
    dag_id="silver_retail_star_schema",
    description="Build Kimball-compliant Silver star schema from Bronze retail data",
    doc_md="""\
        #### Silver Retail Service — Kimball Star Schema

        Builds a dimensional model (star schema) from Bronze data following
        Kimball design patterns.

        **Dimensions** (reference / lookup tables):
        - dim_customer_profile: Customer info (SCD Type 2 — tracks history of changes)
        - dim_product_catalog: Product catalogue
        - dim_supplier: Supplier reference
        - dim_warehouse: Warehouse reference
        - dim_date: Calendar date dimension (static, rarely changes)

        **Facts** (event / measurement tables):
        - fact_order_service: Order transactions
        - fact_inventory_position: Stock-level snapshots
        - fact_customer_engagement: Customer interaction events

        **Execution order**:
        1. Load Date dimension first (no upstream dependencies)
        2. Load remaining dimensions in parallel
        3. Load fact tables after all required dimensions are ready
        4. Run Iceberg maintenance on each table (OPTIMIZE, EXPIRE_SNAPSHOTS, REMOVE_ORPHANS)

        **Trigger**: Automatically runs when any Bronze dataset is updated.
        """,
    start_date=None,
    schedule=TRIGGER_DATASETS,   # Dataset-based trigger instead of cron
    catchup=False,
    default_args=default_args,
    max_active_tasks=DEFAULT_CONFIG["max_active_tasks"],
    tags=["silver", "iceberg", "retail"],
) as dag:
    # ===== TASK CREATION & DEPENDENCIES =====
    build_tasks: Dict[str, SparkSubmitOperator] = {}
    maintenance_tasks: Dict[str, object] = {}

    # Create a (build, maintenance) task pair for every table in the registry
    for builder in TABLE_BUILDERS:
        build_task, maintenance_task = create_silver_task(builder, dag)
        build_tasks[builder.identifier] = build_task
        maintenance_tasks[builder.identifier] = maintenance_task

    # ===== FACT TABLE DEPENDENCIES =====
    # Facts depend on their dimensions being fully built first.
    fact_dependencies = {
        "fact_order_service":        ["dim_date", "dim_customer_profile", "dim_product_catalog"],
        "fact_inventory_position":   ["dim_product_catalog", "dim_warehouse"],
        "fact_customer_engagement":  ["dim_date", "dim_customer_profile", "dim_product_catalog"],
    }

    for fact_identifier, deps in fact_dependencies.items():
        if fact_identifier not in build_tasks:
            continue
        for dep in deps:
            if dep in build_tasks:
                # dimension build → must complete before fact build starts
                build_tasks[dep] >> build_tasks[fact_identifier]

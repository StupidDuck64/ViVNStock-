from airflow.sdk import dag
from cosmos import DbtTaskGroup, ProjectConfig, ProfileConfig, ExecutionConfig
from cosmos.profiles import SparkThriftProfileMapping
import os

# ===== SETUP CONFIGURATION =====
# Airflow connection ID pointing to the Spark Thrift Server (default port 10000)
CONNECTION_ID = "spark_default"

# ===== DBT TARGET SCHEMA =====
# Schema where dbt will create / update models (Iceberg catalog.schema format)
SCHEMA_NAME = "iceberg.data_source"

# ===== DBT PROJECT CONFIGURATION =====
# Path to the dbt project directory (contains dbt_project.yml, models/, tests/, macros/)
DBT_PROJECT_PATH = f"{os.environ['AIRFLOW_HOME']}/dags/dbt"

# ===== DBT EXECUTABLE PATH =====
# Path to the dbt CLI binary inside its isolated virtual environment.
# Isolation avoids dependency conflicts with the Airflow runtime environment.
DBT_EXECUTABLE_PATH = f"{os.environ['AIRFLOW_HOME']}/dbt_venv/bin/dbt"

# ===== SPARK PROFILE CONFIGURATION =====
# Profile = dbt connection settings (similar to a database connection profile)
# ProfileConfig defines profile_name, target_name, and connection details
profile_config = ProfileConfig(
    profile_name="dbt_vib",     # Must match the "profile:" key in dbt_project.yml
    target_name="iceberg",      # dbt target (environment) to run against
    # SparkThriftProfileMapping converts the Airflow connection into a dbt Spark adapter config
    profile_mapping=SparkThriftProfileMapping(
        conn_id=CONNECTION_ID,
        profile_args={"schema": SCHEMA_NAME},
    ),
)

# ===== EXECUTION CONFIGURATION =====
execution_config = ExecutionConfig(
    # Run dbt from its virtual-env binary (allows pinning a different dbt version if needed)
    dbt_executable_path=DBT_EXECUTABLE_PATH,
)

# ===== AIRFLOW DAG DEFINITION =====
@dag(
    schedule=None,     # Manual / externally triggered only
    catchup=False,
    tags=['dbt', 'iceberg', 'spark'],
    # ds_dt is passed as a dbt variable; access in SQL via {{ var('ds_dt') }}
    params={"ds_dt": "2026-01-28"},
)
def dbt_full_project_orchestration():
    """
    Orchestrate all dbt models in a single DAG run.

    Cosmos DbtTaskGroup parses dbt_manifest.json and auto-generates:
    - One Airflow task per dbt model
    - Task groups for macros, seeds, and snapshots
    - Dependency chains from dbt ref() calls in SQL files
    - Test tasks for any defined dbt tests

    Execution flow:
    1. dbt deps  — download packages
    2. dbt seed  — load seed data
    3. dbt run   — run transformations in dependency order
    4. dbt test  — run data-quality checks
    """
    
    # DbtTaskGroup: Cosmos auto-generates the full task graph from the dbt project manifest
    dbt_run_all = DbtTaskGroup(
        group_id="dbt_models",
        project_config=ProjectConfig(DBT_PROJECT_PATH),
        profile_config=profile_config,
        execution_config=execution_config,
        operator_args={
            # Pass Airflow params into dbt as variables; resolved at runtime
            "vars": '{"ds_dt": "{{ params.ds_dt }}"}',
            # Automatically run `dbt deps` before executing models
            "install_deps": True,
        },
        default_args={"retries": 1},  # Retry each dbt task once on failure
    )


# Instantiate the DAG and register it with Airflow
dbt_full_project_orchestration()

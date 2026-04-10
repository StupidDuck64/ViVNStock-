import os
from datetime import datetime
from airflow import DAG
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.operators.python import PythonOperator


# ===== S3 SYNC FUNCTION =====
def sync_from_s3():
    """
    Download files from a MinIO S3 bucket into the local Airflow directories.

    Called on the @hourly schedule to pull the latest DAG and dbt files.
    Uses S3Hook which wraps the boto3 client with the Airflow connection config.

    Steps:
    1. Connect to MinIO via the 'minio' Airflow connection
    2. List objects in the 'airflow' bucket under the dags/ and dbt/ prefixes
    3. Download each file from S3 to the local disk, preserving the folder structure
    4. Skip excluded files (e.g. dag_sync_manager.py itself) to avoid overwriting them

    Side effects:
    - Creates/updates files in /opt/airflow/dags and /opt/airflow/dbt
    - Prints a log line for each successfully synced file
    """
    # ===== S3 CONNECTION =====
    # S3Hook uses the 'minio' Airflow connection to get the endpoint and credentials
    s3 = S3Hook(aws_conn_id='minio')
    
    # ===== BUCKET & BASE PATH =====
    bucket = 'airflow'           # MinIO bucket that holds DAGs and dbt files
    base_path = '/opt/airflow'   # Standard Airflow home directory
    
    # ===== SYNC CONFIGURATION =====
    # Maps each S3 prefix to its corresponding local directory
    sync_config = {
        # S3 dags/ prefix → local dags/ folder
        'dags/': os.path.join(base_path, 'dags'),
        # S3 dbt/ prefix → local dbt/ folder
        'dbt/': os.path.join(base_path, 'dbt')
    }

    # Iterate over each configured prefix and sync its files
    for prefix, local_root in sync_config.items():
        print(f"--- Syncing prefix: {prefix} into {local_root} ---")
        
        # Create the local root directory if it does not already exist
        os.makedirs(local_root, exist_ok=True)
        
        # List all object keys under this prefix
        keys = s3.list_keys(bucket_name=bucket, prefix=prefix)
        
        if not keys:
            print(f"No files found under prefix: {prefix}")
            continue

        for key in keys:
            # Skip this file (dag_sync_manager.py) to avoid overwriting the running DAG,
            # and skip virtual S3 directory entries (keys ending with '/')
            if key == 'dags/dag_sync_manager.py' or key.endswith('/'):
                continue
            
            # Compute the relative path under the prefix, then build the local path
            # e.g. key="dags/staging/my_dag.py" prefix="dags/" → "staging/my_dag.py"
            relative_path = os.path.relpath(key, prefix)
            local_file_path = os.path.join(local_root, relative_path)
            
            # Ensure parent directories exist
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
            
            # Download and write the file
            file_obj = s3.get_key(key, bucket_name=bucket)
            file_content = file_obj.get()['Body'].read()
            
            with open(local_file_path, 'wb') as f:
                f.write(file_content)
                
            print(f"Synced: {key} -> {local_file_path}")


# ===== AIRFLOW DAG DEFINITION =====
with DAG(
    'a_minio_assets_syncer',
    schedule='@hourly',        # Run every hour
    start_date=datetime(2025, 1, 1),
    catchup=False,             # Do not backfill past runs
    tags=['infrastructure', 'minio', 'dbt']
) as dag:
    sync_task = PythonOperator(
        task_id='sync_all_assets',
        python_callable=sync_from_s3,
    )

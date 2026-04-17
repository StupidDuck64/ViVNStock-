import subprocess
import json
import time

container = "lakehouse-oss-vuongngo-airflow-scheduler-1"
dags = [
    "vnstock_bronze_streaming",
    "vnstock_compact_bronze_to_silver",
    "vnstock_backfill_1m_daily",
    "vnstock_backfill_1d_weekly",
    "vnstock_compact_gold_daily"
]

for dag in dags:
    print(f"================ {dag} ================")
    # Fix: use --dag-id instead of -d
    list_runs_cmd = ["docker", "exec", container, "airflow", "dags", "list-runs", "--dag-id", dag, "-o", "json"]
    p_runs = subprocess.run(list_runs_cmd, capture_output=True, text=True)
    
    try:
        runs = json.loads(p_runs.stdout)
        if not runs:
            print("No runs found.")
            continue
            
        # The outputs from previous manual trigger
        # Filter manual triggers we did in 15:17
        manual_runs = [r for r in runs if "manual_fix_2026" in r['run_id']]
        if not manual_runs:
            print("No manual fix runs found.")
            continue
            
        latest_run = manual_runs[-1]
        run_id = latest_run['run_id']
        state = latest_run['state']
        print(f"Run: {run_id} (DAG State: {state})")
        
        # Get tasks for this run
        tasks_cmd = ["docker", "exec", container, "airflow", "tasks", "states-for-dag-run", dag, run_id, "-o", "json"]
        p_tasks = subprocess.run(tasks_cmd, capture_output=True, text=True)
        tasks = json.loads(p_tasks.stdout)
        
        has_failed = False
        for t in tasks:
            if t['state'] == 'failed':
                has_failed = True
                print(f"Task {t['task_id']} FAILED!")
                log_cmd = ["docker", "exec", container, "airflow", "tasks", "render-log", dag, t['task_id'], run_id]
                p_log = subprocess.run(log_cmd, capture_output=True, text=True)
                print("\n".join(p_log.stdout.splitlines()[-60:]))
                print("-" * 50)
            elif t['state'] not in ('success', 'running', 'queued', 'scheduled'):
                print(f"Task {t['task_id']} is {t['state']}")
        
        if not has_failed:
            print("No tasks failed (yet).")
            # print running/queued tasks
            running = [t['task_id'] for t in tasks if t['state'] in ('running', 'queued', 'scheduled')]
            if running:
                 print(f"Still running/queued: {', '.join(running)}")
                
    except Exception as e:
        print(f"Error for {dag}: {e}")
        # print("Stdout:", p_runs.stdout)

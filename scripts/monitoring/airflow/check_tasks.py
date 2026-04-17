import subprocess
import json

container = "lakehouse-oss-vuongngo-airflow-scheduler-1"
runs = {
    "vnstock_bronze_streaming": "manual_fix_20260416T151735Z_vnstock_bronze_streaming",
    "vnstock_compact_bronze_to_silver": "manual_fix_20260416T151735Z_vnstock_compact_bronze_to_silver",
    "vnstock_backfill_1m_daily": "manual_fix_20260416T151735Z_vnstock_backfill_1m_daily",
    "vnstock_backfill_1d_weekly": "manual_fix_20260416T151735Z_vnstock_backfill_1d_weekly",
    "vnstock_compact_gold_daily": "manual_fix_20260416T151735Z_vnstock_compact_gold_daily",
}

for dag, run_id in runs.items():
    print(f"Checking {dag} {run_id}...")
    p = subprocess.run(["docker", "exec", container, "airflow", "tasks", "states-for-dag-run", dag, run_id, "-o", "json"], capture_output=True, text=True)
    if "failed" in p.stdout or "failed" in p.stderr:
        print(f"DAG {dag} has failures.")
        try:
            tasks = json.loads(p.stdout)
            for t in tasks:
                if t["state"] == "failed":
                    print(f"Task {t['task_id']} FAILED")
                    log_cmd = ["docker", "exec", container, "airflow", "tasks", "render-log", dag, t['task_id'], run_id]
                    log_p = subprocess.run(log_cmd, capture_output=True, text=True)
                    print(f"Log tail for {t['task_id']}:")
                    print("\n".join(log_p.stdout.splitlines()[-40:]))
        except Exception as e:
            print(f"Error parsing JSON for {dag}: {e}")
            print("Output tail:", p.stdout[-200:])

import subprocess, json

# Query Prometheus targets API from inside the container
result = subprocess.run(
    ["docker", "exec", "prometheus", "wget", "-qO-", "http://localhost:9090/api/v1/targets"],
    capture_output=True, text=True
)

data = json.loads(result.stdout)
print(f"{'JOB':<22} {'HEALTH':<8} {'LAST_ERROR'}")
print("-" * 80)
for t in data["data"]["activeTargets"]:
    job = t["labels"]["job"]
    health = t["health"]
    err = t.get("lastError", "")
    print(f"{job:<22} {health:<8} {err[:60]}")

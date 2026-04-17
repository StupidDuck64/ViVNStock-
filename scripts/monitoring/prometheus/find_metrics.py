import subprocess, json

# Find actual MinIO metric names
r = subprocess.run(
    ["docker", "exec", "prometheus", "wget", "-qO-",
     "http://localhost:9090/api/v1/label/__name__/values"],
    capture_output=True, text=True
)
data = json.loads(r.stdout)
minio_metrics = [m for m in data["data"] if "minio" in m.lower()]
print(f"=== MinIO metrics in Prometheus ({len(minio_metrics)}) ===")
for m in minio_metrics:
    print(f"  {m}")

# Find actual FastAPI/http metric names
http_metrics = [m for m in data["data"] if "http" in m.lower() or "fastapi" in m.lower()]
print(f"\n=== HTTP/FastAPI metrics ({len(http_metrics)}) ===")
for m in http_metrics:
    print(f"  {m}")

# Find kafka metrics
kafka_metrics = [m for m in data["data"] if "kafka" in m.lower()]
print(f"\n=== Kafka metrics ({len(kafka_metrics)}) ===")
for m in kafka_metrics[:15]:
    print(f"  {m}")

# Find container/cadvisor metrics
container_metrics = [m for m in data["data"] if "container_cpu" in m.lower()]
print(f"\n=== Container CPU metrics ({len(container_metrics)}) ===")
for m in container_metrics:
    print(f"  {m}")

# Find redis metrics
redis_metrics = [m for m in data["data"] if "redis" in m.lower()]
print(f"\n=== Redis metrics ({len(redis_metrics)}) ===")
for m in redis_metrics[:10]:
    print(f"  {m}")

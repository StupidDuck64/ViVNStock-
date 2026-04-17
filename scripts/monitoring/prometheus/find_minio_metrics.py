import subprocess, json

# Query actual minio metrics  
r = subprocess.run(
    ["docker", "exec", "prometheus", "wget", "-qO-",
     "http://localhost:9090/api/v1/label/__name__/values"],
    capture_output=True, text=True
)
data = json.loads(r.stdout)
minio_metrics = [m for m in data["data"] if "minio" in m.lower() or "disk" in m.lower() or "s3" in m.lower() or "bucket" in m.lower()]
print(f"=== MinIO/Disk/S3/Bucket metrics ({len(minio_metrics)}) ===")
for m in sorted(minio_metrics):
    print(f"  {m}")

# Also query directly from minio metrics endpoint
print("\n=== Direct MinIO scrape (first 30 lines with 'disk' or 'free' or 'bucket') ===")
r2 = subprocess.run(
    ["docker", "exec", "prometheus", "wget", "-qO-", "http://minio:9000/minio/v2/metrics/cluster"],
    capture_output=True, text=True
)
lines = r2.stdout.splitlines()
print(f"Total lines from MinIO endpoint: {len(lines)}")
for line in lines:
    if not line.startswith("#") and ("disk" in line.lower() or "free" in line.lower() or "bucket" in line.lower() or "storage" in line.lower()):
        print(f"  {line[:120]}")

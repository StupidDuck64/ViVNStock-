import subprocess, json

# Check Grafana datasources
result = subprocess.run(
    ["docker", "exec", "grafana", "wget", "-qO-", "http://admin:admin@localhost:3000/api/datasources"],
    capture_output=True, text=True
)
print("=== DATASOURCES ===")
try:
    ds = json.loads(result.stdout)
    for d in ds:
        print(f"  Name: {d['name']}, Type: {d['type']}, URL: {d.get('url','N/A')}, Default: {d.get('isDefault', False)}")
except:
    print(result.stdout[:500])
    print("STDERR:", result.stderr[:500])

# Check if prometheus data is actually being collected for minio and fastapi
print("\n=== Query: minio_node_disk_free_bytes ===")
r2 = subprocess.run(
    ["docker", "exec", "prometheus", "wget", "-qO-", "http://localhost:9090/api/v1/query?query=minio_node_disk_free_bytes"],
    capture_output=True, text=True
)
try:
    d2 = json.loads(r2.stdout)
    results = d2["data"]["result"]
    print(f"  Results count: {len(results)}")
    for r in results[:3]:
        print(f"  {r['metric'].get('server','?')}: {r['value'][1]}")
except:
    print(r2.stdout[:300])

print("\n=== Query: http_requests_total ===")
r3 = subprocess.run(
    ["docker", "exec", "prometheus", "wget", "-qO-", "http://localhost:9090/api/v1/query?query=http_requests_total"],
    capture_output=True, text=True
)
try:
    d3 = json.loads(r3.stdout)
    results = d3["data"]["result"]
    print(f"  Results count: {len(results)}")
    for r in results[:3]:
        print(f"  {r['metric']}: {r['value'][1]}")
except:
    print(r3.stdout[:300])

print("\n=== Query: http_request_duration_seconds_bucket ===")
r4 = subprocess.run(
    ["docker", "exec", "prometheus", "wget", "-qO-",
     "http://localhost:9090/api/v1/query?query=http_request_duration_seconds_bucket"],
    capture_output=True, text=True
)
try:
    d4 = json.loads(r4.stdout)
    results = d4["data"]["result"]
    print(f"  Results count: {len(results)}")
except:
    print(r4.stdout[:300])

print("\n=== Query: redis_memory_used_bytes ===")
r5 = subprocess.run(
    ["docker", "exec", "prometheus", "wget", "-qO-",
     "http://localhost:9090/api/v1/query?query=redis_memory_used_bytes"],
    capture_output=True, text=True
)
try:
    d5 = json.loads(r5.stdout)
    results = d5["data"]["result"]
    print(f"  Results count: {len(results)}")
    for r in results[:2]:
        print(f"  {r['value'][1]} bytes")
except:
    print(r5.stdout[:300])

## ⚙️ Generate MinIO Token for Prometheus

- docker exec <minio_container_name> mc alias set local http://localhost:9000 minio minio123
- docker exec <minio_container_name> mc admin prometheus generate local 

Example: 

- docker exec lakehouse-oss-minio-1 mc alias set local http://localhost:9000 minio minio123
- docker exec lakehouse-oss-minio-1 mc admin prometheus generate local

Output: 

scrape_configs:
    - job_name: minio-job
      bearer_token: <YOUR_MINIO_PROMETHEUS_BEARER_TOKEN>
      metrics_path: /minio/v2/metrics/cluster
      scheme: http
      static_configs:
    - targets: ['localhost:9000']

- Copy bearer_token to config/prometheus.yml
# airflow-policy.hcl
# Grants read access to all secrets Airflow needs:
#   - its own credentials (fernet key, web secret, JWT, admin password)
#   - postgres (database connection)
#   - minio (S3 connection for data lake access)
#   - oracle (source DB connection for CDC DAGs)

path "secret/data/platform/airflow" {
  capabilities = ["read"]
}

path "secret/data/platform/postgres" {
  capabilities = ["read"]
}

path "secret/data/platform/minio" {
  capabilities = ["read"]
}

path "secret/data/platform/oracle" {
  capabilities = ["read"]
}

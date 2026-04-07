# postgres-policy.hcl
# Grants read access to PostgreSQL and Hive Metastore credentials.
# Used by: postgres, hive-metastore, debezium services.

path "secret/data/platform/postgres" {
  capabilities = ["read"]
}

path "secret/data/platform/hive-metastore" {
  capabilities = ["read"]
}

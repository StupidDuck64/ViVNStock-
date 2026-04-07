# superset-policy.hcl
# Grants read access to Superset credentials and the databases it queries.
# Used by: superset, superset-worker services.

path "secret/data/platform/superset" {
  capabilities = ["read"]
}

path "secret/data/platform/clickhouse" {
  capabilities = ["read"]
}

path "secret/data/platform/postgres" {
  capabilities = ["read"]
}

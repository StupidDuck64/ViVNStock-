# oracle-policy.hcl
# Grants read access to Oracle source database credentials.
# Used by: airflow (Oracle connection), debezium (Oracle CDC if enabled).

path "secret/data/platform/oracle" {
  capabilities = ["read"]
}

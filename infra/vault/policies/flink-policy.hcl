# flink-policy.hcl
# Grants read access to Flink credentials:
#   - flink: OAuth2/OIDC client secrets
#   - minio: S3 credentials for checkpoints and savepoints (fs.s3a.*)

path "secret/data/platform/flink" {
  capabilities = ["read"]
}

path "secret/data/platform/minio" {
  capabilities = ["read"]
}

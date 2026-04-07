# minio-policy.hcl
# Grants read access to MinIO (S3-compatible) credentials.
# Used by: minio service.

path "secret/data/platform/minio" {
  capabilities = ["read"]
}

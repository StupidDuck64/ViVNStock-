# nifi-policy.hcl
# Grants read access to NiFi credentials.
# Used by: nifi service.

path "secret/data/platform/nifi" {
  capabilities = ["read"]
}

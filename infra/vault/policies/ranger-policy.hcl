# ranger-policy.hcl
# Grants read access to Ranger credentials and Keycloak API secret
# (needed for OIDC integration between Ranger and Keycloak).
# Used by: ranger-admin, ranger-usersync services.

path "secret/data/platform/ranger" {
  capabilities = ["read"]
}

path "secret/data/platform/keycloak" {
  capabilities = ["read"]
}

# keycloak-policy.hcl
# Grants read access to Keycloak admin and database credentials.
# Used by: keycloak, keycloak-init services.

path "secret/data/platform/keycloak" {
  capabilities = ["read"]
}

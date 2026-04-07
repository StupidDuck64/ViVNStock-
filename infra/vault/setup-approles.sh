#!/bin/sh
# =============================================================================
# setup-approles.sh — Enable AppRole auth and create per-service policies
#
# Run AFTER init-secrets.sh has seeded the secrets.
# Idempotent: safe to run multiple times.
#
# Usage (via docker compose):
#   docker compose --profile vault-setup run --rm vault-setup
#
# Usage (manual via docker exec):
#   docker exec -e VAULT_TOKEN=dev-root-token vault \
#     /bin/sh /vault/scripts/setup-approles.sh
# =============================================================================

set -e

export VAULT_ADDR="${VAULT_ADDR:-http://vault:8200}"
export VAULT_TOKEN="${VAULT_TOKEN:-dev-root-token}"

POLICIES_DIR="${POLICIES_DIR:-/vault/policies}"

log() { printf '[vault-setup] %s\n' "$*"; }

# ---------------------------------------------------------------------------
# Wait for Vault
# ---------------------------------------------------------------------------
log "Waiting for Vault at ${VAULT_ADDR} ..."
until vault status > /dev/null 2>&1; do
  sleep 2
done
log "Vault is ready."

# ---------------------------------------------------------------------------
# Enable AppRole auth (idempotent)
# ---------------------------------------------------------------------------
vault auth enable approle 2>/dev/null \
  && log "AppRole auth method enabled." \
  || log "AppRole already enabled — skipping."

# ---------------------------------------------------------------------------
# Helper: write policy file → create AppRole → print credentials
#
# Credentials output:
#   role_id   — static identifier, safe to embed in container env
#   secret_id — treated as a secret, inject at runtime (not committed)
# ---------------------------------------------------------------------------
create_approle() {
  local name="$1"
  local policy_file="${POLICIES_DIR}/$2"

  if [ ! -f "${policy_file}" ]; then
    log "WARNING: ${policy_file} not found — skipping role '${name}'"
    return 0
  fi

  vault policy write "${name}-policy" "${policy_file}"
  log "Policy written: ${name}-policy"

  vault write "auth/approle/role/${name}" \
    token_policies="${name}-policy" \
    token_ttl=1h \
    token_max_ttl=24h \
    secret_id_ttl=0   # non-expiring secret-id (rotate manually in production)

  local role_id
  local secret_id
  role_id=$(vault read -field=role_id "auth/approle/role/${name}/role-id")
  secret_id=$(vault write -force -field=secret_id "auth/approle/role/${name}/secret-id")

  log "AppRole '${name}' ready"
  log "  role_id   = ${role_id}"
  log "  secret_id = ${secret_id}"
  log "  (store secret_id securely — it will not be shown again)"
}

# ---------------------------------------------------------------------------
# Create one AppRole per service group
# ---------------------------------------------------------------------------
create_approle "postgres-svc"   "postgres-policy.hcl"
create_approle "minio-svc"      "minio-policy.hcl"
create_approle "airflow-svc"    "airflow-policy.hcl"
create_approle "keycloak-svc"   "keycloak-policy.hcl"
create_approle "superset-svc"   "superset-policy.hcl"
create_approle "nifi-svc"       "nifi-policy.hcl"
create_approle "flink-svc"      "flink-policy.hcl"
create_approle "ranger-svc"     "ranger-policy.hcl"
create_approle "oracle-svc"     "oracle-policy.hcl"

log "============================================="
log "All AppRoles configured."
log "Next step (Phase 2): inject role_id + secret_id"
log "into each service to replace direct token usage."
log "============================================="

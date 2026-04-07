#!/bin/bash
set -e

# ---------------------------------------------------------------------------
# vault_fetch <kv_path> <field> <default>
#   Reads one field from Vault KV v2 via HTTP API.
#   Falls back to <default> when Vault is unavailable or credentials unset.
# ---------------------------------------------------------------------------
vault_fetch() {
    local path="$1" field="$2" default="$3"
    if [ -z "${VAULT_ADDR:-}" ] || [ -z "${VAULT_TOKEN:-}" ]; then
        printf '%s' "$default"; return
    fi
    local raw val
    raw=$(curl -sf --connect-timeout 3 \
        -H "X-Vault-Token: ${VAULT_TOKEN}" \
        "${VAULT_ADDR}/v1/secret/data/${path}" 2>/dev/null) || true
    val=$(printf '%s' "${raw}" \
        | grep -o "\"${field}\":\"[^\"]*\"" \
        | head -1 \
        | sed 's/^"[^"]*":"\(.*\)"$/\1/')
    printf '%s' "${val:-$default}"
}

# ---------------------------------------------------------------------------
# Resolve secrets for the Ranger Usersync service.
# sync_users.py reads all of these from os.getenv().
# ---------------------------------------------------------------------------
RANGER_ADMIN_PASS=$(vault_fetch "platform/ranger" "admin_pass" \
    "${RANGER_ADMIN_PASS:-Rangeradmin1}")
export RANGER_ADMIN_PASS

KEYCLOAK_ADMIN_PASSWORD=$(vault_fetch "platform/keycloak" "admin_password" \
    "${KEYCLOAK_ADMIN_PASSWORD:-admin123}")
export KEYCLOAK_ADMIN_PASSWORD

KEYCLOAK_ADMIN_API_SECRET=$(vault_fetch "platform/keycloak" "admin_api_secret" \
    "${KEYCLOAK_ADMIN_API_SECRET:-ranger-admin-api-secret-local}")
export KEYCLOAK_ADMIN_API_SECRET

exec python sync_users.py

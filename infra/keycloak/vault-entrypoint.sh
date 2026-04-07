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
# Resolve Keycloak secrets from Vault (falls back to .env / hardcoded values).
# ---------------------------------------------------------------------------
KEYCLOAK_ADMIN_PASSWORD=$(vault_fetch "platform/keycloak" "admin_password" "${KEYCLOAK_ADMIN_PASSWORD:-admin123}")
export KEYCLOAK_ADMIN_PASSWORD

KC_DB_PASSWORD=$(vault_fetch "platform/keycloak" "db_password" "${KC_DB_PASSWORD:-keycloak_pass}")
export KC_DB_PASSWORD

exec /opt/keycloak/bin/kc.sh "$@"

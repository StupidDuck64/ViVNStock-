#!/bin/sh
set -e

# ---------------------------------------------------------------------------
# vault_fetch <kv_path> <field> <default>
#   Reads one field from Vault KV v2 via HTTP API.
#   Uses POSIX sh (Alpine-compatible — no bash required).
#   Falls back to <default> when Vault is unavailable or credentials unset.
# ---------------------------------------------------------------------------
vault_fetch() {
    _path="$1"; _field="$2"; _default="$3"
    if [ -z "${VAULT_ADDR:-}" ] || [ -z "${VAULT_TOKEN:-}" ]; then
        printf '%s' "$_default"; return
    fi
    _raw=$(curl -sf --connect-timeout 3 \
        -H "X-Vault-Token: ${VAULT_TOKEN}" \
        "${VAULT_ADDR}/v1/secret/data/${_path}" 2>/dev/null) || true
    _val=$(printf '%s' "${_raw}" \
        | grep -o "\"${_field}\":\"[^\"]*\"" \
        | head -1 \
        | sed 's/^"[^"]*":"\(.*\)"$/\1/')
    printf '%s' "${_val:-$_default}"
}

# ---------------------------------------------------------------------------
# Resolve the Keycloak DB password from Vault.
# POSTGRES_PASSWORD is the variable postgres:15-alpine expects.
# ---------------------------------------------------------------------------
POSTGRES_PASSWORD=$(vault_fetch "platform/keycloak" "db_password" "${POSTGRES_PASSWORD:-keycloak_pass}")
export POSTGRES_PASSWORD

exec docker-entrypoint.sh postgres

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
# Resolve NiFi single-user credentials from Vault.
# NiFi reads SINGLE_USER_CREDENTIALS_PASSWORD at startup to configure
# the single-user login provider in conf/login-identity-providers.xml.
# Password must be >= 12 characters (NiFi requirement).
# ---------------------------------------------------------------------------
SINGLE_USER_CREDENTIALS_PASSWORD=$(vault_fetch \
    "platform/nifi" "admin_password" \
    "${SINGLE_USER_CREDENTIALS_PASSWORD:-adminadminadmin}")
export SINGLE_USER_CREDENTIALS_PASSWORD

exec /opt/nifi/scripts/start.sh

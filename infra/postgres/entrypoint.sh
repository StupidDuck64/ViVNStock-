#!/bin/bash
set -e

# ---------------------------------------------------------------------------
# vault_fetch <kv_path> <field> <default>
#   Reads one field from Vault KV v2 via HTTP API.
#   Falls back to <default> when:
#     - VAULT_ADDR or VAULT_TOKEN env vars are not set, OR
#     - Vault is unreachable (connect-timeout 3s to avoid startup delay), OR
#     - The field is not present in the response.
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
# Resolve secrets: Vault takes priority; .env value is the fallback.
# ---------------------------------------------------------------------------
POSTGRES_PASSWORD=$(vault_fetch "platform/postgres" "password" "${POSTGRES_PASSWORD:-}")
export POSTGRES_PASSWORD

POSTGRES_CDC_PASSWORD=$(vault_fetch "platform/postgres" "cdc_password" "${POSTGRES_CDC_PASSWORD:-cdc_reader_pwd}")
export POSTGRES_CDC_PASSWORD

docker-entrypoint.sh postgres &
POSTGRES_PID=$!

/init-databases.sh

wait $POSTGRES_PID

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
# Resolve ClickHouse credentials from Vault (falls back to .env values).
# The ClickHouse docker entrypoint reads CLICKHOUSE_USER + CLICKHOUSE_PASSWORD
# and writes /etc/clickhouse-server/users.d/default-password.xml, which
# overrides any hardcoded password in users.xml (users.d/ takes precedence).
# ---------------------------------------------------------------------------
CLICKHOUSE_PASSWORD=$(vault_fetch "platform/clickhouse" "password" "${CLICKHOUSE_PASSWORD:-admin}")
export CLICKHOUSE_PASSWORD

exec /entrypoint.sh "$@"

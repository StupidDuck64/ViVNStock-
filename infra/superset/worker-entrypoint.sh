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
# Resolve Superset secret key from Vault (required by Celery worker too).
# ---------------------------------------------------------------------------
SUPERSET_SECRET_KEY=$(vault_fetch "platform/superset" "secret_key" "${SUPERSET_SECRET_KEY:-your_superset_key}")
export SUPERSET_SECRET_KEY
export SECRET_KEY="${SUPERSET_SECRET_KEY}"

POSTGRES_PASSWORD=$(vault_fetch "platform/postgres" "password" "${POSTGRES_PASSWORD:-admin}")
export POSTGRES_PASSWORD

# Start Celery worker
exec celery --app=superset.tasks.celery_app:app worker --pool=prefork -O fair -c 4

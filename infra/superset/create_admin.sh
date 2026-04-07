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
# Resolve Superset secrets and database password from Vault.
# ---------------------------------------------------------------------------
SUPERSET_SECRET_KEY=$(vault_fetch "platform/superset" "secret_key" "${SUPERSET_SECRET_KEY:-your_superset_key}")
export SUPERSET_SECRET_KEY
# SECRET_KEY is the variable Superset/Flask reads from config; keep in sync.
export SECRET_KEY="${SUPERSET_SECRET_KEY}"

SUPERSET_ADMIN_PASSWORD=$(vault_fetch "platform/superset" "admin_password" "${SUPERSET_ADMIN_PASSWORD:-admin}")
export SUPERSET_ADMIN_PASSWORD

# POSTGRES_PASSWORD is read by superset_config.py to build SQLALCHEMY_DATABASE_URI.
POSTGRES_PASSWORD=$(vault_fetch "platform/postgres" "password" "${POSTGRES_PASSWORD:-admin}")
export POSTGRES_PASSWORD

superset db upgrade

superset fab create-admin \
  --username "${SUPERSET_ADMIN_USERNAME:-admin}" \
  --firstname "${SUPERSET_ADMIN_FIRSTNAME:-Admin}" \
  --lastname "${SUPERSET_ADMIN_LASTNAME:-User}" \
  --email "${SUPERSET_ADMIN_EMAIL:-admin@superset.com}" \
  --password "${SUPERSET_ADMIN_PASSWORD:-admin}" || true
superset init
superset import_datasources -p /app/provisioning/databases.yaml || true
exec superset run -h 0.0.0.0 -p 8088

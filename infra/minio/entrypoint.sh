#!/bin/bash
set -e

# ---------------------------------------------------------------------------
# vault_fetch <kv_path> <field> <default>
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
# Resolve MinIO root credentials from Vault (falls back to .env values)
# ---------------------------------------------------------------------------
MINIO_ROOT_USER=$(vault_fetch "platform/minio" "root_user" "${MINIO_ROOT_USER:-minio}")
export MINIO_ROOT_USER

MINIO_ROOT_PASSWORD=$(vault_fetch "platform/minio" "root_password" "${MINIO_ROOT_PASSWORD:-minio123}")
export MINIO_ROOT_PASSWORD

minio server /data --console-address ":9001" &
/usr/local/bin/setup-minio.sh
wait

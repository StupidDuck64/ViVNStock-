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
# Flink OAuth2 client secret (used by flink-jobmanager).
# FLINK_PROPERTIES is a multiline YAML string that Flink's docker entrypoint
# writes to flink-conf.yaml. We patch the secret line in-place before Flink
# reads it, so no plaintext secret ever touches the compose file.
# The sed patterns are no-ops on lines that don't match — safe to run on
# both jobmanager and taskmanager FLINK_PROPERTIES.
# ---------------------------------------------------------------------------
_FLINK_OAUTH2_SECRET=$(vault_fetch \
    "platform/flink" "oauth2_client_secret" \
    "${FLINK_OAUTH2_CLIENT_SECRET:-CHANGE_ME_FLINK_SECRET}")

# ---------------------------------------------------------------------------
# MinIO / S3 credentials (used by flink-taskmanager fs.s3a.*).
# ---------------------------------------------------------------------------
_MINIO_ACCESS=$(vault_fetch \
    "platform/minio" "root_user" \
    "${MINIO_ROOT_USER:-minio}")
_MINIO_SECRET=$(vault_fetch \
    "platform/minio" "root_password" \
    "${MINIO_ROOT_PASSWORD:-minio123}")

# ---------------------------------------------------------------------------
# Patch FLINK_PROPERTIES in-place (sed is a no-op when pattern is absent).
# ---------------------------------------------------------------------------
if [ -n "${FLINK_PROPERTIES:-}" ]; then
    FLINK_PROPERTIES=$(printf '%s\n' "${FLINK_PROPERTIES}" \
        | sed "s|security.oauth2.client.secret:.*|security.oauth2.client.secret: ${_FLINK_OAUTH2_SECRET}|" \
        | sed "s|fs.s3a.access.key:.*|fs.s3a.access.key: ${_MINIO_ACCESS}|" \
        | sed "s|fs.s3a.secret.key:.*|fs.s3a.secret.key: ${_MINIO_SECRET}|")
    export FLINK_PROPERTIES
fi

exec "$@"

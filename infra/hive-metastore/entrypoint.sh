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
# Resolve secrets: Vault takes priority; .env value / hardcoded default is the fallback.
# Must be set BEFORE the := defaults below so they become no-ops.
# ---------------------------------------------------------------------------
HIVE_METASTORE_DB_PASS=$(vault_fetch "platform/hive-metastore" "db_pass" "${HIVE_METASTORE_DB_PASS:-admin}")
export HIVE_METASTORE_DB_PASS

export HOME=/tmp/hive
mkdir -p "$HOME"

export HIVE_CONF_DIR=/opt/hive/conf

: "${HIVE_METASTORE_DB_TYPE:=postgres}"
: "${HIVE_METASTORE_DB_HOST:=postgres}"
: "${HIVE_METASTORE_DB_NAME:=metastore}"
: "${HIVE_METASTORE_DB_USER:=admin}"
: "${HIVE_METASTORE_DB_PASS:=admin}"  # no-op: already resolved above
: "${HIVE_METASTORE_DB_PORT:=5432}"

if [[ "${HIVE_METASTORE_DB_TYPE}" == "postgres" ]]; then
  JDBC_URL="jdbc:postgresql://${HIVE_METASTORE_DB_HOST}:${HIVE_METASTORE_DB_PORT}/${HIVE_METASTORE_DB_NAME}"
else
  JDBC_URL="jdbc:${HIVE_METASTORE_DB_TYPE}://${HIVE_METASTORE_DB_HOST}:${HIVE_METASTORE_DB_PORT}/${HIVE_METASTORE_DB_NAME}"
fi

echo "[INFO] Checking Hive Metastore schema..."

if /opt/hive/bin/schematool \
    -dbType "${HIVE_METASTORE_DB_TYPE}" \
    -url "${JDBC_URL}" \
    -userName "${HIVE_METASTORE_DB_USER}" \
    -passWord "${HIVE_METASTORE_DB_PASS}" \
    -info >/dev/null 2>&1; then
  echo "[INFO] Schema đã tồn tại. Bỏ qua khởi tạo."
else
  echo "[INFO] Schema chưa tồn tại. Tiến hành khởi tạo."
  /opt/hive/bin/schematool \
    -dbType "${HIVE_METASTORE_DB_TYPE}" \
    -url "${JDBC_URL}" \
    -userName "${HIVE_METASTORE_DB_USER}" \
    -passWord "${HIVE_METASTORE_DB_PASS}" \
    -initSchema
fi

apt-get update && apt-get install -y gzip dos2unix

RANGER_VERSION=ranger-2.7.1-SNAPSHOT-hive-plugin
cd /opt/hive
mkdir -p /opt/hive/${RANGER_VERSION} && \
tar xvf ${RANGER_VERSION}.tar.gz --strip-components=1 -C ${RANGER_VERSION} && \
yes | cp -rf install.properties ${RANGER_VERSION}/ && \
chown root:root -R ${RANGER_VERSION}/* && \
dos2unix /opt/hive/${RANGER_VERSION}/enable-hive-plugin.sh && \
./${RANGER_VERSION}/enable-hive-plugin.sh


exec /opt/hive/bin/hive --service metastore

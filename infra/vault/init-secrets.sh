#!/bin/sh
# =============================================================================
# init-secrets.sh — Seed all platform secrets into Vault KV v2
#
# Runs automatically via the `vault-init` service on `docker compose up`.
# Idempotent: safe to run multiple times — existing values are overwritten.
#
# Secrets are read from environment variables (injected via env_file: .env).
# Defaults match the current hardcoded values in docker-compose.yml so the
# platform works out-of-the-box even without a customised .env.
# =============================================================================

set -e

export VAULT_ADDR="${VAULT_ADDR:-http://vault:8200}"
export VAULT_TOKEN="${VAULT_TOKEN:-dev-root-token}"

log() { printf '[vault-init] %s\n' "$*"; }

# ---------------------------------------------------------------------------
# Wait for Vault server to be ready
# ---------------------------------------------------------------------------
log "Waiting for Vault at ${VAULT_ADDR} ..."
until vault status > /dev/null 2>&1; do
  sleep 2
done
log "Vault is ready."

# ---------------------------------------------------------------------------
# Enable KV v2 secrets engine at secret/ (idempotent)
# In dev mode Vault 1.12+ already enables KV v2 at secret/ — safe to skip.
# ---------------------------------------------------------------------------
vault secrets enable -version=2 -path=secret kv 2>/dev/null \
  && log "KV v2 enabled at secret/" \
  || log "KV v2 already enabled at secret/ — skipping."

# ---------------------------------------------------------------------------
# PostgreSQL / CDC user
# ---------------------------------------------------------------------------
vault kv put secret/platform/postgres \
  password="${POSTGRES_PASSWORD:-admin}" \
  cdc_password="${POSTGRES_CDC_PASSWORD:-cdc_reader_pwd}"
log "Wrote secret/platform/postgres"

# ---------------------------------------------------------------------------
# Hive Metastore (shares postgres credentials but stored separately for RBAC)
# ---------------------------------------------------------------------------
vault kv put secret/platform/hive-metastore \
  db_user="${HIVE_METASTORE_DB_USER:-admin}" \
  db_pass="${HIVE_METASTORE_DB_PASS:-admin}"
log "Wrote secret/platform/hive-metastore"

# ---------------------------------------------------------------------------
# MinIO (S3-compatible object storage) — also used by Spark & Flink
# ---------------------------------------------------------------------------
vault kv put secret/platform/minio \
  root_user="${MINIO_ROOT_USER:-minio}" \
  root_password="${MINIO_ROOT_PASSWORD:-minio123}"
log "Wrote secret/platform/minio"

# ---------------------------------------------------------------------------
# ClickHouse (analytics database)
# ---------------------------------------------------------------------------
vault kv put secret/platform/clickhouse \
  user="${CLICKHOUSE_USER:-admin}" \
  password="${CLICKHOUSE_PASSWORD:-admin}"
log "Wrote secret/platform/clickhouse"

# ---------------------------------------------------------------------------
# Apache Airflow
#
# NOTE: AIRFLOW_FERNET_KEY is not defined in .env but is required by Airflow.
# The default below is a placeholder — generate a production value with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Then set AIRFLOW_FERNET_KEY in .env before running `docker compose up`.
# ---------------------------------------------------------------------------
vault kv put secret/platform/airflow \
  admin_password="${AIRFLOW_ADMIN_PASSWORD:-airflow}" \
  webserver_secret_key="${AIRFLOW_WEBSERVER_SECRET_KEY:-lRy7FcBzEmGMuLiTPr2Skz9y65vnKQZQF80JEYQKcVA=}" \
  api_secret_key="${AIRFLOW_API_SECRET_KEY:-lRy7FcBzEmGMuLiTPr2Skz9y65vnKQZQF80JEYQKcVA=}" \
  jwt_secret_key="${AIRFLOW__API_AUTH__JWT_SECRET_KEY:-lRy7FcBzEmGMuLiTPr2Skz9y65vnKQZQF80JEYQKcVA=}" \
  fernet_key="${AIRFLOW_FERNET_KEY:-jJ/9sz0g0OHxsfxOoSfdFdmk3ysNmPRnH3TUAbz3IHA=}" \
  db_conn_dsn="${AIRFLOW_DATABASE_SQL_ALCHEMY_CONN:-postgresql+psycopg2://admin:admin@postgres/metastore}" \
  celery_result_backend="${AIRFLOW_CELERY_RESULT_BACKEND:-db+postgresql://admin:admin@postgres/metastore}"
log "Wrote secret/platform/airflow"

# ---------------------------------------------------------------------------
# Keycloak (IAM)
# admin_password / db_password are hardcoded in docker-compose.yml.
# Override by setting KEYCLOAK_ADMIN_PASSWORD / KC_DB_PASSWORD in .env.
# ---------------------------------------------------------------------------
vault kv put secret/platform/keycloak \
  admin_password="${KEYCLOAK_ADMIN_PASSWORD:-admin123}" \
  db_password="${KC_DB_PASSWORD:-keycloak_pass}" \
  admin_api_secret="${KEYCLOAK_ADMIN_API_SECRET:-ranger-admin-api-secret-local}"
log "Wrote secret/platform/keycloak"

# ---------------------------------------------------------------------------
# Apache Superset
# ---------------------------------------------------------------------------
vault kv put secret/platform/superset \
  secret_key="${SUPERSET_SECRET_KEY:-your_superset_key}" \
  admin_password="${SUPERSET_ADMIN_PASSWORD:-admin}"
log "Wrote secret/platform/superset"

# ---------------------------------------------------------------------------
# Apache NiFi
# Password must be ≥ 12 characters (NiFi requirement).
# ---------------------------------------------------------------------------
vault kv put secret/platform/nifi \
  admin_password="${NIFI_ADMIN_PASSWORD:-adminadminadmin}"
log "Wrote secret/platform/nifi"

# ---------------------------------------------------------------------------
# Apache Flink (OAuth2 / OIDC via Keycloak)
# Default values are placeholders — must be replaced before production use.
# ---------------------------------------------------------------------------
vault kv put secret/platform/flink \
  oauth2_client_secret="${FLINK_OAUTH2_CLIENT_SECRET:-CHANGE_ME_FLINK_SECRET}" \
  nginx_oidc_client_secret="${FLINK_NGINX_OIDC_CLIENT_SECRET:-CHANGE_ME_FLINK_CLIENT_SECRET}"
log "Wrote secret/platform/flink"

# ---------------------------------------------------------------------------
# Apache Ranger (authorization)
# ---------------------------------------------------------------------------
vault kv put secret/platform/ranger \
  admin_pass="${RANGER_ADMIN_PASS:-Rangeradmin1}" \
  oauth2_secret="${RANGER_OAUTH2_SECRET:-CHANGE_ME_RANGER_SECRET}"
log "Wrote secret/platform/ranger"

# ---------------------------------------------------------------------------
# Oracle (external source database for CDC)
# Host is also stored here to avoid leaking network topology in docker-compose.
# ---------------------------------------------------------------------------
vault kv put secret/platform/oracle \
  host="${ORACLE_HOST:-192.168.26.180}" \
  user="${ORACLE_USER:-PG_T24CORE}" \
  password="${ORACLE_PASSWORD:-PG_T24CORE}"
log "Wrote secret/platform/oracle"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
log "============================================="
log "All secrets seeded successfully!"
log "Vault UI  : http://localhost:8200"
log "Token     : ${VAULT_TOKEN}"
log "Verify    : vault kv list secret/platform/"
log "============================================="

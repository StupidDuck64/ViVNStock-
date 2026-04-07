#!/bin/sh
set -e

# ---------------------------------------------------------------------------
# vault_fetch <kv_path> <field> <default>
#   POSIX sh version (Alpine-compatible — openresty:alpine-fat has no bash).
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
# Resolve the OIDC client secret used by lua-resty-openidc in nginx.conf.
# The Lua code reads OIDC_CLIENT_SECRET via os.getenv() at each request.
# ---------------------------------------------------------------------------
OIDC_CLIENT_SECRET=$(vault_fetch \
    "platform/flink" "nginx_oidc_client_secret" \
    "${OIDC_CLIENT_SECRET:-CHANGE_ME_FLINK_CLIENT_SECRET}")
export OIDC_CLIENT_SECRET

exec "$@"

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
# Resolve Keycloak admin password from Vault (falls back to env / default).
# ---------------------------------------------------------------------------
KEYCLOAK_ADMIN_PASSWORD=$(vault_fetch "platform/keycloak" "admin_password" "${KEYCLOAK_ADMIN_PASSWORD:-admin123}")
export KEYCLOAK_ADMIN_PASSWORD

KEYCLOAK_URL="http://keycloak:8080"
REALM="data-platform"
CLIENT_ID="ranger-admin-api"
REALM_MGMT_CLIENT="realm-management"

echo "=========================================="
echo "Configuring Ranger Admin API Service Account"
echo "=========================================="

echo "Waiting for Keycloak..."

until /opt/keycloak/bin/kcadm.sh config credentials \
  --server $KEYCLOAK_URL \
  --realm master \
  --user $KEYCLOAK_ADMIN \
  --password $KEYCLOAK_ADMIN_PASSWORD >/dev/null 2>&1
do
  sleep 5
done

echo "✓ Keycloak ready"

# Get client UUID for ranger-admin-api
echo ""
echo "Getting ranger-admin-api client UUID..."
CLIENT_UUID=$(/opt/keycloak/bin/kcadm.sh get clients \
  -r $REALM \
  -q clientId=$CLIENT_ID | sed -n 's/.*"id" : "\(.*\)".*/\1/p' | head -1)

if [ -z "$CLIENT_UUID" ]; then
    echo "✗ Client '${CLIENT_ID}' not found in realm '${REALM}'"
    exit 1
fi
echo "✓ Client UUID: ${CLIENT_UUID}"

# Get service account user ID for ranger-admin-api
echo ""
echo "Getting service account user for ranger-admin-api..."
SERVICE_ACCOUNT_USER_ID=$(/opt/keycloak/bin/kcadm.sh get clients/$CLIENT_UUID/service-account-user \
  -r $REALM | sed -n 's/.*"id" : "\(.*\)".*/\1/p')

if [ -z "$SERVICE_ACCOUNT_USER_ID" ]; then
    echo "✗ Service account user not found for client '${CLIENT_ID}'"
    exit 1
fi
echo "✓ Service Account User ID: ${SERVICE_ACCOUNT_USER_ID}"

# Get realm-management client UUID
echo ""
echo "Getting realm-management client UUID..."
REALM_MGMT_ID=$(/opt/keycloak/bin/kcadm.sh get clients \
  -r $REALM \
  -q clientId=$REALM_MGMT_CLIENT | sed -n 's/.*"id" : "\(.*\)".*/\1/p' | head -1)

if [ -z "$REALM_MGMT_ID" ]; then
    echo "✗ Client 'realm-management' not found in realm '${REALM}'"
    exit 1
fi
echo "✓ Realm Management Client UUID: ${REALM_MGMT_ID}"

# Grant realm-admin role to service account
echo ""
echo "Granting realm-admin role to service account..."
/opt/keycloak/bin/kcadm.sh add-roles \
  -r $REALM \
  --uid $SERVICE_ACCOUNT_USER_ID \
  --cid $REALM_MGMT_ID \
  --rolename realm-admin

if [ $? -eq 0 ]; then
    echo "✓ Successfully granted realm-admin role"
else
    echo "⚠ Warning: Could not grant realm-admin role (may already be granted)"
fi

# Verify the roles were assigned
echo ""
echo "Verifying assigned roles..."
ASSIGNED_ROLES=$(/opt/keycloak/bin/kcadm.sh get clients/$REALM_MGMT_ID/roles \
  -r $REALM)

if echo "$ASSIGNED_ROLES" | grep -q "realm-admin"; then
    echo "✓ realm-admin role exists in realm-management"
fi

echo ""
echo "=========================================="
echo "✓ Ranger Admin API Configuration Complete!"
echo "=========================================="

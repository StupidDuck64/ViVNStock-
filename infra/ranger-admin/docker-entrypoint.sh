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
# Resolve Ranger and Keycloak secrets from Vault.
# These are used both by install.properties patching below and by the
# Python helper scripts (trino_service_setup.py, trino-service.json).
# ---------------------------------------------------------------------------
RANGER_ADMIN_PASS=$(vault_fetch "platform/ranger" "admin_pass" \
    "${RANGER_ADMIN_PASS:-Rangeradmin1}")
export RANGER_ADMIN_PASS

RANGER_OAUTH2_SECRET=$(vault_fetch "platform/ranger" "oauth2_secret" \
    "${RANGER_OAUTH2_SECRET:-CHANGE_ME_RANGER_SECRET}")
export RANGER_OAUTH2_SECRET

KEYCLOAK_ADMIN_API_SECRET=$(vault_fetch "platform/keycloak" "admin_api_secret" \
    "${KEYCLOAK_ADMIN_API_SECRET:-ranger-admin-api-secret-local}")
export KEYCLOAK_ADMIN_API_SECRET

echo "=========================================="
echo "Starting Ranger Admin Setup"
echo "=========================================="

RANGER_VERSION=2.7.1-SNAPSHOT
TAR_FILE=ranger-${RANGER_VERSION}-admin.tar.gz
DOWNLOAD_URL=https://github.com/aakashnand/trino-ranger-demo/releases/download/trino-ranger-demo-v1.0/${TAR_FILE}

# --------------------
# STEP 1: Download Ranger
# --------------------
echo "[1/9] Checking Ranger tarball..."
if [ -f "$TAR_FILE" ]; then
    echo "✓ Tar file already exists."
else
    echo "→ Downloading..."
    wget -q --show-progress $DOWNLOAD_URL -O $TAR_FILE || {
        echo "✗ Download failed"
        exit 1
    }
    echo "✓ Download completed."
fi

# --------------------
# STEP 2: Extract
# --------------------
echo "[2/9] Extracting Ranger..."
if [ -d "/root/ranger-${RANGER_VERSION}-admin" ]; then
    rm -rf /root/ranger-${RANGER_VERSION}-admin
fi
tar xzf $TAR_FILE -C /root/
echo "✓ Extraction completed."

RANGER_DIR="/root/ranger-${RANGER_VERSION}-admin"

# --------------------
# STEP 3: Download/Verify JDBC in ALL locations FIRST
# --------------------
echo "[3/9] Setting up PostgreSQL JDBC driver in ALL locations..."

# Ensure we have the JDBC jar
if [ ! -f "/root/postgresql.jar" ]; then
    echo "→ Downloading JDBC driver..."
    wget -O /root/postgresql.jar https://jdbc.postgresql.org/download/postgresql-42.7.3.jar || {
        echo "✗ JDBC download failed"
        exit 1
    }
fi

echo "✓ JDBC source: $(ls -lh /root/postgresql.jar | awk '{print $5}')"

# Create ALL necessary directories
mkdir -p ${RANGER_DIR}/lib
mkdir -p ${RANGER_DIR}/jisql/lib
mkdir -p ${RANGER_DIR}/ews/lib
mkdir -p ${RANGER_DIR}/ews/webapp/WEB-INF/lib

# Copy to ALL possible locations Ranger might check
echo "→ Copying JDBC to all locations..."
cp /root/postgresql.jar ${RANGER_DIR}/lib/postgresql.jar
cp /root/postgresql.jar ${RANGER_DIR}/jisql/lib/postgresql.jar
cp /root/postgresql.jar ${RANGER_DIR}/ews/lib/postgresql.jar
cp /root/postgresql.jar ${RANGER_DIR}/ews/webapp/WEB-INF/lib/postgresql.jar

# Also keep the original location
cp /root/postgresql.jar /root/postgresql.jar.backup

# Verify all copies
ALL_OK=true
for loc in lib jisql/lib ews/lib ews/webapp/WEB-INF/lib; do
    if [ -f "${RANGER_DIR}/${loc}/postgresql.jar" ]; then
        echo "  ✓ ${loc}/postgresql.jar ($(stat -c%s ${RANGER_DIR}/${loc}/postgresql.jar) bytes)"
    else
        echo "  ✗ Failed: ${loc}/postgresql.jar"
        ALL_OK=false
    fi
done

if [ "$ALL_OK" = false ]; then
    echo "✗ JDBC setup incomplete"
    exit 1
fi

echo "✓ JDBC driver ready in all locations"

# --------------------
# STEP 4: Copy and FIX install.properties
# --------------------
echo "[4/9] Configuring install.properties..."

if [ ! -f "/root/ranger-admin/install.properties" ]; then
    echo "✗ install.properties not found!"
    exit 1
fi

# Copy the file
cp /root/ranger-admin/install.properties ${RANGER_DIR}/install.properties

# # NOW FIX IT IN PLACE
cd ${RANGER_DIR}

# Fix DB_FLAVOR (must be uppercase)
sed -i 's/^DB_FLAVOR=postgres$/DB_FLAVOR=POSTGRES/' install.properties

# Fix db_host
sed -i 's/^db_host=psql01$/db_host=postgres/' install.properties

# Fix db_root_user  
sed -i 's/^db_root_user=admin$/db_root_user=admin/' install.properties

# Fix db_name
sed -i 's/^db_name=admin$/db_name=ranger/' install.properties

# Fix db_user
sed -i 's/^db_user=admin$/db_user=rangeradmin/' install.properties

# Fix db_password
sed -i 's/^db_password=admin$/db_password=rangeradmin/' install.properties

# Patch rangerAdmin_password (and related passwords) using runtime secret from Vault.
# rangerAdmin_password must be >= 8 chars with at least one letter and one digit.
sed -i "s|^rangerAdmin_password=.*|rangerAdmin_password=${RANGER_ADMIN_PASS}|" install.properties
sed -i "s|^rangerTagsync_password=.*|rangerTagsync_password=${RANGER_ADMIN_PASS}|" install.properties
sed -i "s|^rangerUsersync_password=.*|rangerUsersync_password=${RANGER_ADMIN_PASS}|" install.properties
sed -i "s|^keyadmin_password=.*|keyadmin_password=${RANGER_ADMIN_PASS}|" install.properties

# CRITICAL: Fix SQL_CONNECTOR_JAR to use lib directory (not /root)
sed -i "s|^SQL_CONNECTOR_JAR=.*|SQL_CONNECTOR_JAR=${RANGER_DIR}/lib/postgresql.jar|" install.properties

# Remove any trailing whitespace or hidden characters
sed -i 's/[[:space:]]*$//' install.properties

# Fix Elasticsearch URL if needed
# sed -i 's|^audit_elasticsearch_urls=.*|audit_elasticsearch_urls=http://elasticsearch:9200|' install.properties

echo "→ Verifying critical settings..."
echo "-------------------------------------------"
grep "^DB_FLAVOR=" install.properties
grep "^SQL_CONNECTOR_JAR=" install.properties
grep "^db_host=" install.properties
grep "^db_name=" install.properties
grep "^db_user=" install.properties
echo "-------------------------------------------"

# Double-check the JDBC path in properties exists
JDBC_PATH=$(grep "^SQL_CONNECTOR_JAR=" install.properties | cut -d'=' -f2)
if [ ! -f "$JDBC_PATH" ]; then
    echo "✗ ERROR: JDBC not found at configured path: $JDBC_PATH"
    echo "→ Available JDBC files:"
    find ${RANGER_DIR} -name "postgresql.jar" -ls
    exit 1
fi

echo "✓ install.properties configured and verified"

# --------------------
# STEP 5: Database connectivity check
# --------------------
echo "[5/9] Checking database connectivity..."
DB_HOST=$(grep "^db_host=" install.properties | cut -d'=' -f2)
echo "→ Testing connection to ${DB_HOST}:5432..."

MAX_WAIT=30
COUNT=0
while [ $COUNT -lt $MAX_WAIT ]; do
    if timeout 2 bash -c "echo > /dev/tcp/${DB_HOST}/5432" 2>/dev/null; then
        echo "✓ Database is reachable!"
        break
    fi
    echo -n "."
    sleep 2
    COUNT=$((COUNT+1))
done

if [ $COUNT -ge $MAX_WAIT ]; then
    echo "⚠ Warning: Could not verify database connectivity"
fi

# --------------------
# STEP 6: Patch db_setup.py if needed (WORKAROUND)
# --------------------
echo "[6/9] Applying workarounds to Ranger setup scripts..."

# Sometimes db_setup.py has issues with JDBC path checking
# Let's ensure it can find the JDBC jar
if [ -f "${RANGER_DIR}/db_setup.py" ]; then
    echo "→ Checking db_setup.py for JDBC validation..."
    
    # Create a symlink as additional safety
    ln -sf ${RANGER_DIR}/lib/postgresql.jar /usr/share/java/postgresql.jar 2>/dev/null || true
    ln -sf ${RANGER_DIR}/lib/postgresql.jar /opt/postgresql.jar 2>/dev/null || true
    
    echo "✓ Workarounds applied"
fi

# --------------------
# STEP 7: Run setup.sh with debug
# --------------------
echo "[7/9] Running Ranger setup.sh..."

# Set CLASSPATH to include JDBC
export CLASSPATH="${RANGER_DIR}/lib/postgresql.jar:${CLASSPATH:-}"

# Run setup
./setup.sh 2>&1 | tee /tmp/ranger-setup.log

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "✗ Ranger setup failed!"
    echo ""
    echo "Last 30 lines of setup log:"
    tail -30 /tmp/ranger-setup.log
    echo ""
    echo "Checking JDBC configuration:"
    grep -E "CONNECTOR|postgresql|does not exists" /tmp/ranger-setup.log | tail -10
    exit 1
fi

echo "✓ Ranger setup completed successfully"

# --------------------
# STEP 8: Start Ranger
# --------------------
echo "[8/9] Starting Ranger Admin..."

ranger-admin start || {
    echo "✗ Failed to start Ranger Admin"
    exit 1
}

echo "→ Waiting for Ranger to be ready..."
MAX_WAIT=60
COUNT=0
while [ $COUNT -lt $MAX_WAIT ]; do
    if curl -sf http://localhost:6080/ > /dev/null 2>&1; then
        echo "✓ Ranger Admin is ready!"
        break
    fi
    echo -n "."
    sleep 2
    COUNT=$((COUNT+1))
done

# --------------------
# STEP 9: Python setup (if needed)
# --------------------
echo "[9/9] Setting up Trino service (if configured)..."

REQUIREMENTS_FILE="/root/ranger-admin/requirements.txt"
[ ! -f "$REQUIREMENTS_FILE" ] && REQUIREMENTS_FILE="/root/ranger-admin/requirement.txt"

if [ -f "$REQUIREMENTS_FILE" ]; then
    if [ ! -d "/root/ranger-admin/.venv" ]; then
        python3 -m venv /root/ranger-admin/.venv
    fi
    
    source /root/ranger-admin/.venv/bin/activate
    pip install --upgrade pip > /dev/null 2>&1
    pip install -r $REQUIREMENTS_FILE || true
    
    if [ -f "/root/ranger-admin/trino_service_setup.py" ]; then
        python /root/ranger-admin/trino_service_setup.py || echo "⚠ Trino setup skipped"
    fi
    
    deactivate
else
    echo "⚠ No requirements.txt found, skipping Python setup"
fi

# --------------------
# FINAL: Tail logs
# --------------------
echo ""
echo "=========================================="
echo "✓ Ranger Admin Setup Completed!"
echo "=========================================="
echo "URL: http://localhost:6080"
echo "Credentials: admin / admin"
echo ""
echo "Tailing logs..."
echo "=========================================="

LOG_FILE=$(ls -t ${RANGER_DIR}/ews/logs/ranger-admin-*.log 2>/dev/null | head -1)
if [ -n "$LOG_FILE" ]; then
    tail -f "$LOG_FILE"
else
    tail -f /dev/null
fi
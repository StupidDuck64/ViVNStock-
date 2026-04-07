#!/bin/bash
set -euo pipefail

PGHOST="${POSTGRES_HOST:-localhost}"
PGUSER="${POSTGRES_USER:-postgres}"
PGDB="${POSTGRES_DB:-postgres}"
REPLICATION_ROLE="${POSTGRES_CDC_USER:-cdc_reader}"
REPLICATION_PASSWORD="${POSTGRES_CDC_PASSWORD:-cdc_reader_pwd}"

# Ranger specific variables
RANGER_DB="${RANGER_DB:-ranger}"
RANGER_USER="${RANGER_USER:-rangeradmin}"
RANGER_PASSWORD="${RANGER_PASSWORD:-rangeradmin}"

escape_sql_literal() {
  printf "%s" "$1" | sed "s/'/''/g"
}

escape_sql_identifier() {
  printf "%s" "$1" | sed 's/"/""/g'
}

echo "=============================================="
echo "PostgreSQL Database Initialization Script"
echo "=============================================="
echo ""

# Wait for PostgreSQL to be ready
echo "[1/5] Waiting for PostgreSQL to be ready..."
until pg_isready -U "$PGUSER" -d "$PGDB" -h "$PGHOST" >/dev/null 2>&1; do
  echo "  → Waiting for PostgreSQL..."
  sleep 2
done
echo "  ✓ PostgreSQL is ready!"
echo ""

# ============================================
# Create demo database (original functionality)
# ============================================
echo "[2/5] Checking/creating required databases..."

if ! psql -U "$PGUSER" -d "$PGDB" -tAc "SELECT 1 FROM pg_database WHERE datname = 'demo'" | grep -q 1; then
  echo "  → Creating demo database..."
  psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 -c "CREATE DATABASE demo;"
  echo "  ✓ Demo database created"
else
  echo "  ✓ Demo database already exists"
fi

# ============================================
# Create Ranger database (NEW)
# ============================================
if ! psql -U "$PGUSER" -d "$PGDB" -tAc "SELECT 1 FROM pg_database WHERE datname = '${RANGER_DB}'" | grep -q 1; then
  echo "  → Creating ${RANGER_DB} database..."
  psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${RANGER_DB};"
  echo "  ✓ ${RANGER_DB} database created"
else
  echo "  ✓ ${RANGER_DB} database already exists"
fi

# ============================================
# Create Superset database
# ============================================
if ! psql -U "$PGUSER" -d "$PGDB" -tAc "SELECT 1 FROM pg_database WHERE datname = 'superset'" | grep -q 1; then
  echo "  → Creating superset database..."
  psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 -c "CREATE DATABASE superset;"
  echo "  ✓ Superset database created"
else
  echo "  ✓ Superset database already exists"
fi

echo ""

# ============================================
# Configure logical replication
# ============================================
echo "[3/5] Configuring logical replication parameters..."
psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 <<'EOSQL'
ALTER SYSTEM SET wal_level = 'logical';
ALTER SYSTEM SET max_replication_slots = '16';
ALTER SYSTEM SET max_wal_senders = '16';
ALTER SYSTEM SET wal_keep_size = '256MB';
SELECT pg_reload_conf();
EOSQL
echo "  ✓ Replication parameters configured"
echo ""

# ============================================
# Create replication role for CDC
# ============================================
echo "[4/5] Creating database users..."

# CDC replication role
echo "  → Checking CDC replication role..."
escaped_role_literal=$(escape_sql_literal "$REPLICATION_ROLE")
escaped_role_identifier=$(escape_sql_identifier "$REPLICATION_ROLE")
escaped_pwd_literal=$(escape_sql_literal "$REPLICATION_PASSWORD")

role_exists=$(psql -U "$PGUSER" -d "$PGDB" -At -v ON_ERROR_STOP=1 \
  -c "SELECT 1 FROM pg_roles WHERE rolname = '${escaped_role_literal}' LIMIT 1;")
role_exists=$(printf "%s" "$role_exists" | tr -d '[:space:]')

if [[ "$role_exists" != "1" ]]; then
  psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 \
    -c "CREATE ROLE \"${escaped_role_identifier}\" WITH LOGIN PASSWORD '${escaped_pwd_literal}' REPLICATION;"
  echo "  ✓ CDC replication role created"
else
  psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 \
    -c "ALTER ROLE \"${escaped_role_identifier}\" WITH LOGIN PASSWORD '${escaped_pwd_literal}' REPLICATION;"
  echo "  ✓ CDC replication role updated"
fi

# ============================================
# Create Ranger database user (NEW)
# ============================================
echo "  → Checking Ranger database user..."
escaped_ranger_user_literal=$(escape_sql_literal "$RANGER_USER")
escaped_ranger_user_identifier=$(escape_sql_identifier "$RANGER_USER")
escaped_ranger_pwd_literal=$(escape_sql_literal "$RANGER_PASSWORD")

ranger_user_exists=$(psql -U "$PGUSER" -d "$PGDB" -At -v ON_ERROR_STOP=1 \
  -c "SELECT 1 FROM pg_roles WHERE rolname = '${escaped_ranger_user_literal}' LIMIT 1;")
ranger_user_exists=$(printf "%s" "$ranger_user_exists" | tr -d '[:space:]')

if [[ "$ranger_user_exists" != "1" ]]; then
  psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 \
    -c "CREATE ROLE \"${escaped_ranger_user_identifier}\" WITH LOGIN PASSWORD '${escaped_ranger_pwd_literal}';"
  echo "  ✓ Ranger user created"
else
  psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 \
    -c "ALTER ROLE \"${escaped_ranger_user_identifier}\" WITH LOGIN PASSWORD '${escaped_ranger_pwd_literal}';"
  echo "  ✓ Ranger user updated"
fi

# Grant privileges on Ranger database
echo "  → Granting privileges on ${RANGER_DB} database..."
psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 << EOSQL
GRANT ALL PRIVILEGES ON DATABASE ${RANGER_DB} TO "${escaped_ranger_user_identifier}";
ALTER DATABASE ${RANGER_DB} OWNER TO "${escaped_ranger_user_identifier}";
EOSQL
echo "  ✓ Ranger user privileges granted"
echo ""

# ============================================
# Setup demo database tables
# ============================================
echo "[5/5] Setting up demo database tables and permissions..."

psql -U "$PGUSER" -d demo -v ON_ERROR_STOP=1 -v replication_role="$REPLICATION_ROLE" <<EOSQL
-- ===== Core OLTP tables (match generator canvas) =====

CREATE TABLE IF NOT EXISTS users(
  user_id    TEXT PRIMARY KEY,
  email      TEXT UNIQUE NOT NULL,
  country    TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS products(
  product_id TEXT PRIMARY KEY,
  title      TEXT NOT NULL,
  category   TEXT,
  price_usd  NUMERIC(10,2),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Legacy/global inventory snapshot (kept for simple sums)
CREATE TABLE IF NOT EXISTS inventory(
  product_id TEXT PRIMARY KEY REFERENCES products(product_id),
  qty        INT NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS warehouses(
  warehouse_id TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  country      TEXT,
  region       TEXT
);

CREATE TABLE IF NOT EXISTS suppliers(
  supplier_id TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  country     TEXT,
  rating      NUMERIC(3,2)
);

CREATE TABLE IF NOT EXISTS customer_segments(
  user_id         TEXT PRIMARY KEY REFERENCES users(user_id),
  segment         TEXT,
  lifetime_value  NUMERIC(12,2)
);

-- Multi-location stock (authoritative inventory-by-location)
CREATE TABLE IF NOT EXISTS warehouse_inventory(
  warehouse_id TEXT REFERENCES warehouses(warehouse_id),
  product_id   TEXT REFERENCES products(product_id),
  qty          INT NOT NULL,
  reserved_qty INT NOT NULL DEFAULT 0,
  updated_at   TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (warehouse_id, product_id)
);

CREATE TABLE IF NOT EXISTS product_suppliers(
  product_id      TEXT REFERENCES products(product_id),
  supplier_id     TEXT REFERENCES suppliers(supplier_id),
  cost_usd        NUMERIC(10,2),
  lead_time_days  INT,
  PRIMARY KEY(product_id, supplier_id)
);

-- ===== Indexes (idempotent) =====
CREATE INDEX IF NOT EXISTS idx_users_country         ON users(country);
CREATE INDEX IF NOT EXISTS idx_users_created         ON users(created_at);

CREATE INDEX IF NOT EXISTS ix_products_category      ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_updated      ON products(updated_at);

CREATE INDEX IF NOT EXISTS idx_inventory_qty         ON inventory(qty);
CREATE INDEX IF NOT EXISTS idx_inventory_updated     ON inventory(updated_at);

CREATE INDEX IF NOT EXISTS idx_warehouses_country    ON warehouses(country);
CREATE INDEX IF NOT EXISTS idx_suppliers_country     ON suppliers(country);
CREATE INDEX IF NOT EXISTS idx_suppliers_rating      ON suppliers(rating);

CREATE INDEX IF NOT EXISTS idx_product_suppliers_cost ON product_suppliers(cost_usd);

CREATE INDEX IF NOT EXISTS ix_whinv_product          ON warehouse_inventory(product_id);
CREATE INDEX IF NOT EXISTS idx_warehouse_inventory_qty ON warehouse_inventory(qty);

CREATE INDEX IF NOT EXISTS idx_customer_segments_segment ON customer_segments(segment);
CREATE INDEX IF NOT EXISTS idx_customer_segments_ltv     ON customer_segments(lifetime_value);

-- ===== Grants (safe if run multiple times) =====
GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO "$PGUSER";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "$PGUSER";

-- Ensure future objects are also accessible
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON TABLES    TO "$PGUSER";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON SEQUENCES TO "$PGUSER";

GRANT CONNECT ON DATABASE demo TO :"replication_role";
GRANT USAGE ON SCHEMA public TO :"replication_role";
GRANT SELECT ON ALL TABLES IN SCHEMA public TO :"replication_role";
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO :"replication_role";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO :"replication_role";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON SEQUENCES TO :"replication_role";
EOSQL

echo "  ✓ Demo tables and indexes created"
echo ""

# ============================================
# Setup CDC publication
# ============================================
echo "Ensuring CDC publication exists..."
publication_exists=$(psql -U "$PGUSER" -d demo -At -v ON_ERROR_STOP=1 \
  -c "SELECT 1 FROM pg_publication WHERE pubname = 'demo_publication' LIMIT 1;")
publication_exists=$(printf "%s" "$publication_exists" | tr -d '[:space:]')

if [[ "$publication_exists" != "1" ]]; then
  psql -U "$PGUSER" -d demo -v ON_ERROR_STOP=1 \
    -c "CREATE PUBLICATION demo_publication FOR TABLES IN SCHEMA public;"
  echo "  ✓ CDC publication created"
else
  psql -U "$PGUSER" -d demo -v ON_ERROR_STOP=1 \
    -c "ALTER PUBLICATION demo_publication SET TABLES IN SCHEMA public;"
  echo "  ✓ CDC publication updated"
fi
echo ""

# ============================================
# Summary
# ============================================
echo "=============================================="
echo "✓ Database setup complete!"
echo "=============================================="
echo ""
echo "Databases created:"
echo "  • demo     - Application database with CDC enabled"
echo "  • ${RANGER_DB}  - Ranger Admin database"
echo ""
echo "Users created:"
echo "  • ${REPLICATION_ROLE} - CDC replication user"
echo "  • ${RANGER_USER}  - Ranger database user"
echo ""
echo "To verify:"
echo "  psql -U postgres -c '\\l'"
echo "  psql -U postgres -d ${RANGER_DB} -c '\\dt'"
echo "  psql -U postgres -d demo -c '\\dt'"
echo ""
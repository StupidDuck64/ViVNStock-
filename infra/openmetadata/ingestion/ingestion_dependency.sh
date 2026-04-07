#!/usr/bin/env bash

#  Copyright 2025 Collate
#  Licensed under the Collate Community License, Version 1.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  https://github.com/open-metadata/OpenMetadata/blob/main/ingestion/LICENSE
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

set -e

DB_HOST=${DB_HOST:-postgresql}
DB_PORT=${DB_PORT:-5432}

AIRFLOW_DB=${AIRFLOW_DB:-airflow_db}
DB_USER=${DB_USER:-airflow_user}
DB_SCHEME=${DB_SCHEME:-postgresql+psycopg2}
DB_PASSWORD=${DB_PASSWORD:-airflow_pass}
DB_PROPERTIES=${DB_PROPERTIES:-""}

AIRFLOW_ADMIN_USER=${AIRFLOW_ADMIN_USER:-admin}
AIRFLOW_ADMIN_PASSWORD=${AIRFLOW_ADMIN_PASSWORD:-admin}

# URL encode credentials for database connection
DB_USER_VAR=`echo "${DB_USER}" | python3 -c "import urllib.parse; encoded_user = urllib.parse.quote(input()); print(encoded_user)"`
DB_PASSWORD_VAR=`echo "${DB_PASSWORD}" | python3 -c "import urllib.parse; encoded_user = urllib.parse.quote(input()); print(encoded_user)"`

DB_CONN=`echo -n "${DB_SCHEME}://${DB_USER_VAR}:${DB_PASSWORD_VAR}@${DB_HOST}:${DB_PORT}/${AIRFLOW_DB}${DB_PROPERTIES}"`

# Airflow 3.x configuration
export AIRFLOW__API__AUTH_BACKENDS=${AIRFLOW__API__AUTH_BACKENDS:-"airflow.api.auth.backend.basic_auth,airflow.api.auth.backend.session"}
export AIRFLOW__API__BASE_URL=${AIRFLOW__API__BASE_URL:-"http://localhost:8080"}

# Enable CSRF for API endpoints (required for production security)
export AIRFLOW__API__ENABLE_CSRF=${AIRFLOW__API__ENABLE_CSRF:-"True"}

# Configure SimpleAuthManager for Airflow 3.x
echo "Configuring SimpleAuthManager (default in Airflow 3.x)..."
export AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_USERS="${AIRFLOW_ADMIN_USER}:admin"

AIRFLOW_HOME=${AIRFLOW_HOME:-/opt/airflow}
export AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_PASSWORDS_FILE="${AIRFLOW_HOME}/simple_auth_manager_passwords.json"

# Configure database connection for Airflow 3.x
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=${AIRFLOW__DATABASE__SQL_ALCHEMY_CONN:-$DB_CONN}

# Install required dependencies FIRST before any airflow command
echo "Installing required Airflow and database dependencies..."
pip install --no-cache-dir asyncpg 2>/dev/null || echo "asyncpg install attempted"

echo "Installing Airflow providers..."
pip install --no-cache-dir \
    apache-airflow-providers-apache-kafka \
    apache-airflow-providers-postgres \
    apache-airflow-providers-http \
    cachetools \
    2>/dev/null || echo "Dependencies install attempted"

# Migrate Airflow database
echo "Running Airflow database migration..."
airflow db migrate

# Create SimpleAuthManager password file
echo "Setting up SimpleAuthManager credentials..."
PASSWORD_FILE="${AIRFLOW_HOME}/simple_auth_manager_passwords.json"

python3 << EOF
import json
import os
from pathlib import Path

password_file = Path('${AIRFLOW_HOME}/simple_auth_manager_passwords.json')
passwords = {}

if password_file.exists():
    try:
        with open(password_file, 'r') as f:
            passwords = json.load(f)
    except:
        pass

passwords['${AIRFLOW_ADMIN_USER}'] = '${AIRFLOW_ADMIN_PASSWORD}'

with open(password_file, 'w') as f:
    json.dump(passwords, f, indent=2)

print(f"Password set for ${AIRFLOW_ADMIN_USER}")
EOF

# Ensure log directory exists
mkdir -p /opt/airflow/logs

# Remove stale PID files
rm -f /opt/airflow/airflow-webserver-monitor.pid

# Install OpenMetadata providers if needed
echo "Installing OpenMetadata Airflow provider..."
pip install --no-cache-dir openmetadata-airflow-provider 2>/dev/null || echo "Provider install attempted"

echo "Starting Airflow 3.x API Server..."
echo "API Server running on port 8080..."

# Start Airflow API Server (main entry point for Airflow 3.x)
exec airflow api-server --port 8080

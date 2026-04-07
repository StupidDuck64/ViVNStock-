FROM apache/superset:latest

USER root

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libkrb5-dev \
    libssl-dev \
    dos2unix \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    apt-get install -y bash python3-pip curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install packages using pip3 (system pip)
# This should install into the site-packages that Python can find
RUN curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py && \
    /app/.venv/bin/python /tmp/get-pip.py && \
    rm /tmp/get-pip.py

# Install Python dependencies into Superset's venv using uv
ENV VIRTUAL_ENV=/app/.venv
RUN uv pip install \
    authlib \
    flask-oauthlib \
    requests-oauthlib \
    "sqlalchemy>=1.4.0,<2.0.0" \
    "trino>=0.328.0" \
    "sqlalchemy-trino>=0.5.0" \
    "clickhouse-connect>=0.7.0" \
    "redis" \
    "psycopg2-binary"

# Create directories
RUN mkdir -p /app/pythonpath /app/provisioning

# Copy entrypoint scripts and config
COPY create_admin.sh /app/pythonpath/create_admin.sh
COPY worker-entrypoint.sh /app/pythonpath/worker-entrypoint.sh
COPY superset_config.py /app/pythonpath/superset_config.py
COPY provisioning/ /app/provisioning/

# Fix line endings and make scripts executable
RUN dos2unix /app/pythonpath/*.sh && \
    chmod +x /app/pythonpath/create_admin.sh && \
    chmod +x /app/pythonpath/worker-entrypoint.sh
# Switch to superset user
USER superset

# Set environment
ENV PYTHONPATH=/app/pythonpath:$PYTHONPATH
ENV SUPERSET_CONFIG_PATH=/app/pythonpath/superset_config.py

ENTRYPOINT ["/app/pythonpath/create_admin.sh"]
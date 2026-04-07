FROM python:3.11-slim

WORKDIR /app

COPY sync_users.py .
COPY vault-entrypoint.sh /vault-entrypoint.sh

RUN pip install requests psycopg2-binary && \
    apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/* && \
    chmod +x /vault-entrypoint.sh

ENTRYPOINT ["/bin/bash", "/vault-entrypoint.sh"]
FROM postgres:16

# curl is needed by the vault_fetch helper in entrypoint.sh
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY init-databases.sh /init-databases.sh
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /init-databases.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

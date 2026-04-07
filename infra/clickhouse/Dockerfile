FROM clickhouse/clickhouse-server:25.12
COPY config.xml /etc/clickhouse-server/config.xml
COPY users.xml /etc/clickhouse-server/users.xml
COPY vault-entrypoint.sh /vault-entrypoint.sh
RUN chmod +x /vault-entrypoint.sh

EXPOSE 8123 9000
ENTRYPOINT ["/vault-entrypoint.sh"]

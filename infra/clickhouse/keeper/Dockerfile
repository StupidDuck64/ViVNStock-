FROM clickhouse/clickhouse-keeper:25.1

# Install netcat for healthcheck (Alpine uses apk)
RUN apk add --no-cache netcat-openbsd

COPY keeper_config.xml /etc/clickhouse-keeper/keeper_config.xml
EXPOSE 9181 9234
CMD ["clickhouse-keeper", "--config-file=/etc/clickhouse-keeper/keeper_config.xml"]

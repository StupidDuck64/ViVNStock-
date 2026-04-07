FROM apache/hive:3.1.3
USER root

ENV SKIP_SCHEMA_INIT=true

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl wget ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Sử dụng phiên bản 3.2.0 để ổn định hơn với Hive 3.1.3 và tránh lỗi IOStatistics (chỉ có từ 3.3.0+)
ARG HADOOP_AWS_VERSION=3.2.0
ARG AWS_SDK_VERSION=1.11.375

RUN mkdir -p /tmp/deps && \
    curl -o /tmp/deps/hadoop-aws-${HADOOP_AWS_VERSION}.jar \
    https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/${HADOOP_AWS_VERSION}/hadoop-aws-${HADOOP_AWS_VERSION}.jar && \
    curl -o /tmp/deps/aws-java-sdk-bundle-${AWS_SDK_VERSION}.jar \
    https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/${AWS_SDK_VERSION}/aws-java-sdk-bundle-${AWS_SDK_VERSION}.jar && \
    curl -o /tmp/deps/iceberg-hive-runtime-1.9.2.jar \
    https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-hive-runtime/1.9.2/iceberg-hive-runtime-1.9.2.jar && \
    # Copy vào cả Hive lib và Hadoop lib để đảm bảo classpath đồng nhất
    cp /tmp/deps/*.jar /opt/hive/lib/ && \
    rm -rf /tmp/deps

# [cite_start]Download PostgreSQL JDBC driver [cite: 1, 2]
RUN wget -q https://jdbc.postgresql.org/download/postgresql-42.7.3.jar -O /opt/hive/lib/postgres.jar && \
    chmod 644 /opt/hive/lib/postgres.jar && \
    chown hive:hive /opt/hive/lib/postgres.jar

COPY config/ /opt/hive/conf/
COPY entrypoint.sh /opt/hive/entrypoint.sh
# COPY ranger-2.7.1-SNAPSHOT-hive-plugin.tar.gz /opt/hive/ranger-2.7.1-SNAPSHOT-hive-plugin.tar.gz
COPY ranger-2.7.0-hive-plugin.tar.gz /opt/hive/ranger-2.7.0-hive-plugin.tar.gz
COPY install.properties /opt/hive/install.properties
RUN chmod 644 /opt/hive/lib/*.jar /opt/hive/conf/*.xml
RUN chmod +x /opt/hive/entrypoint.sh

USER root

ENTRYPOINT ["/opt/hive/entrypoint.sh"]
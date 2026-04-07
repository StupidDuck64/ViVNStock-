FROM bitnamilegacy/spark:3.5.6

USER 0

RUN useradd -u 1001 -m -s /bin/bash spark && \
    chown -R 1001:1001 ${SPARK_HOME}

ENV HOME=/home/spark
ENV USER=spark
ENV HADOOP_USER_NAME=spark

RUN pip install --no-cache-dir pyarrow pandas fastavro confluent-kafka[avro] vnstock redis

# Tải Hive 3.1.3 jars từ Maven Central
ENV HIVE_VERSION=3.1.3

RUN set -eux; \
    mkdir -p /tmp/hive-jars; \
    curl -fSL -o /tmp/hive-jars/hive-metastore-${HIVE_VERSION}.jar \
      "https://repo1.maven.org/maven2/org/apache/hive/hive-metastore/${HIVE_VERSION}/hive-metastore-${HIVE_VERSION}.jar"; \
    curl -fSL -o /tmp/hive-jars/hive-exec-${HIVE_VERSION}-core.jar \
      "https://repo1.maven.org/maven2/org/apache/hive/hive-exec/${HIVE_VERSION}/hive-exec-${HIVE_VERSION}-core.jar"; \
    curl -fSL -o /tmp/hive-jars/hive-common-${HIVE_VERSION}.jar \
      "https://repo1.maven.org/maven2/org/apache/hive/hive-common/${HIVE_VERSION}/hive-common-${HIVE_VERSION}.jar"; \
    curl -fSL -o /tmp/hive-jars/hive-serde-${HIVE_VERSION}.jar \
      "https://repo1.maven.org/maven2/org/apache/hive/hive-serde/${HIVE_VERSION}/hive-serde-${HIVE_VERSION}.jar"; \
    curl -fSL -o /tmp/hive-jars/hive-standalone-metastore-${HIVE_VERSION}.jar \
      "https://repo1.maven.org/maven2/org/apache/hive/hive-standalone-metastore/${HIVE_VERSION}/hive-standalone-metastore-${HIVE_VERSION}.jar"; \
    curl -fSL -o /tmp/hive-jars/libthrift-0.9.3.jar \
      "https://repo1.maven.org/maven2/org/apache/thrift/libthrift/0.9.3/libthrift-0.9.3.jar"; \
    curl -fSL -o /tmp/hive-jars/libfb303-0.9.3.jar \
      "https://repo1.maven.org/maven2/org/apache/thrift/libfb303/0.9.3/libfb303-0.9.3.jar"; \
    curl -fSL -o /tmp/hive-jars/hive-shims-common-${HIVE_VERSION}.jar \
      "https://repo1.maven.org/maven2/org/apache/hive/shims/hive-shims-common/${HIVE_VERSION}/hive-shims-common-${HIVE_VERSION}.jar"; \
    curl -fSL -o /tmp/hive-jars/hive-shims-0.23-${HIVE_VERSION}.jar \
      "https://repo1.maven.org/maven2/org/apache/hive/shims/hive-shims-0.23/${HIVE_VERSION}/hive-shims-0.23-${HIVE_VERSION}.jar"; \
    curl -fSL -o /tmp/hive-jars/hive-shims-${HIVE_VERSION}.jar \
      "https://repo1.maven.org/maven2/org/apache/hive/hive-shims/${HIVE_VERSION}/hive-shims-${HIVE_VERSION}.jar"; \
    curl -fSL -o /tmp/hive-jars/hive-storage-api-2.7.2.jar \
      "https://repo1.maven.org/maven2/org/apache/hive/hive-storage-api/2.7.2/hive-storage-api-2.7.2.jar"; \
    cp /tmp/hive-jars/*.jar ${SPARK_HOME}/jars/; \
    rm -rf /tmp/hive-jars

RUN set -eux; \
    mkdir -p "${SPARK_HOME}/jars"; \
    curl -fSL -o "${SPARK_HOME}/jars/spark-sql-kafka-0-10_2.12-3.5.0.jar" "https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.0/spark-sql-kafka-0-10_2.12-3.5.0.jar"; \
    curl -fSL -o "${SPARK_HOME}/jars/spark-token-provider-kafka-0-10_2.12-3.5.0.jar" "https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.0/spark-token-provider-kafka-0-10_2.12-3.5.0.jar"; \
    curl -fSL -o "${SPARK_HOME}/jars/kafka-clients-3.5.0.jar" "https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.5.0/kafka-clients-3.5.0.jar"; \
    curl -fSL -o "${SPARK_HOME}/jars/commons-pool2-2.12.0.jar" "https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.12.0/commons-pool2-2.12.0.jar"; \
    curl -fSL -o "${SPARK_HOME}/jars/iceberg-spark-runtime-3.5_2.12-1.9.2.jar" "https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-3.5_2.12/1.9.2/iceberg-spark-runtime-3.5_2.12-1.9.2.jar"; \
    curl -fSL -o "${SPARK_HOME}/jars/iceberg-aws-bundle-1.9.2.jar" "https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-aws-bundle/1.9.2/iceberg-aws-bundle-1.9.2.jar"; \
    curl -fSL -o "${SPARK_HOME}/jars/hadoop-aws-3.3.4.jar" "https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar"; \
    curl -fSL -o "${SPARK_HOME}/jars/aws-java-sdk-bundle-1.12.791.jar" "https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.791/aws-java-sdk-bundle-1.12.791.jar"; \
    curl -fSL -o "${SPARK_HOME}/jars/spark-avro_2.12-3.5.0.jar" "https://repo1.maven.org/maven2/org/apache/spark/spark-avro_2.12/3.5.0/spark-avro_2.12-3.5.0.jar"

RUN curl -L https://repo1.maven.org/maven2/com/oracle/database/jdbc/ojdbc8/21.9.0.0/ojdbc8-21.9.0.0.jar -o /opt/bitnami/spark/jars/ojdbc8.jar

RUN curl -L https://repo1.maven.org/maven2/com/clickhouse/clickhouse-jdbc/0.8.5/clickhouse-jdbc-0.8.5-all.jar -o /opt/bitnami/spark/jars/clickhouse-jdbc-0.8.5-all.jar

COPY spark-defaults.conf ${SPARK_HOME}/conf/spark-defaults.conf

RUN chown -R 1001:1001 ${SPARK_HOME}/conf

ENV SPARK_JARS_DIR="${SPARK_HOME}/jars"
ENV PYTHONPATH="/opt/spark/jobs:${PYTHONPATH}"

USER 1001

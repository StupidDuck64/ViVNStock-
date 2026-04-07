#!/bin/bash
set -e

echo "=== Creating required directories ==="
mkdir -p /opt/hive
mkdir -p /opt/bitnami/spark/conf
mkdir -p /var/log/hive/audit
mkdir -p /tmp/ranger/hivedev/policycache

echo "=== Verifying Ranger XML files exist ==="
# Các file đã được copy vào /opt/bitnami/spark/conf/ bởi Dockerfile
if [ -f "/opt/bitnami/spark/conf/ranger-hive-security.xml" ]; then
    echo "✓ ranger-hive-security.xml found"
else
    echo "✗ ranger-hive-security.xml NOT found"
fi

if [ -f "/opt/bitnami/spark/conf/ranger-hive-audit.xml" ]; then
    echo "✓ ranger-hive-audit.xml found"
else
    echo "✗ ranger-hive-audit.xml NOT found"
fi

echo "=== Installing Ranger Plugin ==="
RANGER_VERSION=ranger-2.7.1-SNAPSHOT-hive-plugin

cd /opt/hive
tar xvf /opt/${RANGER_VERSION}.tar.gz --strip-components=1 -C .
cp -f /opt/install.properties .

if [ -f ./enable-hive-plugin.sh ]; then
    dos2unix ./enable-hive-plugin.sh 2>/dev/null || true
    chmod +x ./enable-hive-plugin.sh
    
    # Sửa COMPONENT_INSTALL_DIR trong script để trỏ đúng
    sed -i 's|COMPONENT_INSTALL_DIR=.*|COMPONENT_INSTALL_DIR=/opt/bitnami/spark|g' enable-hive-plugin.sh 2>/dev/null || true
    
    echo "=== Running enable-hive-plugin.sh ==="
    ./enable-hive-plugin.sh || echo "Warning: Plugin installation had issues"
fi

echo "=== Copying Ranger JARs to Spark ==="
if [ -d "./lib" ]; then
    echo "Copying JAR files from /opt/hive/lib to /opt/spark/jars/"
    cp -v ./lib/*.jar /opt/bitnami/spark/jars/ 2>/dev/null || echo "No ranger JAR files found"
    cp -v ./install/lib/*.jar /opt/bitnami/spark/jars/ 2>/dev/null || echo "No ranger JAR files found"
    cp -v ./lib/ranger-hive-plugin-impl/*.jar /opt/bitnami/spark/jars/ 2>/dev/null || echo "No ranger JAR files found"
    cp -v ./lib/eclipselink*.jar /opt/bitnami/spark/jars/ 2>/dev/null || echo "No eclipselink JAR files found"
    cp -v ./lib/commons-configuration*.jar /opt/bitnami/spark/jars/ 2>/dev/null || echo "No commons-configuration JAR files found"
else
    echo "Warning: /opt/hive/lib directory not found"
fi

echo "=== Verifying Ranger Installation ==="
echo ""
echo "Config files in /opt/bitnami/spark/conf/:"
ls -lah /opt/bitnami/spark/conf/ranger-* 2>/dev/null || echo "No ranger config files found"

echo ""
echo "JAR files in /opt/bitnami/spark/jars/:"
ls -lah /opt/bitnami/spark/jars/ranger-* 2>/dev/null || echo "No ranger JAR files found"

echo ""
echo "All XML files in conf:"
ls -lah /opt/bitnami/spark/conf/*.xml 2>/dev/null || echo "No XML files found"  
echo "=== Setting permissions ==="
chmod -R 755 /tmp/ranger 2>/dev/null || true
chown -R spark:spark /tmp/ranger 2>/dev/null || true

echo "=== Starting Spark Thrift Server ==="
/opt/bitnami/spark/sbin/start-thriftserver.sh \
  --master spark://spark-master:7077 \
  --name "Spark Thrift Server Iceberg" \
  --hiveconf hive.server2.thrift.port=10000 \
  --hiveconf hive.server2.thrift.bind.host=0.0.0.0 \
  --hiveconf hive.server2.authentication=NONE \
  --hiveconf hive.server2.enable.doAs=false \
  --hiveconf hive.security.authorization.enabled=true \
  --hiveconf hive.security.authorization.manager=org.apache.ranger.authorization.hive.authorizer.RangerHiveAuthorizerFactory \
  --hiveconf hive.security.authenticator.manager=org.apache.hadoop.hive.ql.security.SessionStateUserAuthenticator \
  --conf spark.sql.catalog.iceberg=org.apache.iceberg.spark.SparkCatalog \
  --conf spark.sql.catalog.iceberg.type=hive \
  --conf spark.sql.catalog.iceberg.uri=thrift://hive-metastore:9083 \
  --conf spark.sql.catalog.iceberg.warehouse=s3a://iceberg/ \
  --conf spark.hadoop.fs.s3a.endpoint=http://minio:9000 \
  --conf spark.hadoop.fs.s3a.access.key=minio \
  --conf spark.hadoop.fs.s3a.secret.key=minio123 \
  --conf spark.hadoop.fs.s3a.path.style.access=true \
  --conf spark.sql.catalog.iceberg.s3.endpoint=http://minio:9000 \
  --conf spark.sql.catalog.iceberg.s3.access-key-id=minio \
  --conf spark.sql.catalog.iceberg.s3.secret-access-key=minio123 \
  --conf spark.sql.catalog.iceberg.s3.path-style-access=true \
  --conf spark.sql.catalog.oracle_db=org.apache.spark.sql.execution.datasources.v2.jdbc.JDBCTableCatalog \
  --conf spark.sql.catalog.oracle_db.url=jdbc:oracle:thin:@//192.168.26.180:1521/dbpdb \
  --conf spark.sql.catalog.oracle_db.user=PG_T24CORE \
  --conf spark.sql.catalog.oracle_db.password=PG_T24CORE \
  --conf spark.sql.catalog.oracle_db.driver=oracle.jdbc.driver.OracleDriver \
  --conf spark.sql.catalog.oracle_db.pushDownPredicate=true \
  --conf spark.sql.catalog.oracle_db.pushDownAggregate=true \
  --conf spark.sql.catalog.oracle_db.pushDownFilters=true \
  --conf spark.sql.catalog.oracle_db.fetchsize=10000 \
  --conf spark.sql.catalog.clickhouse=org.apache.spark.sql.execution.datasources.v2.jdbc.JDBCTableCatalog \
  --conf spark.sql.catalog.clickhouse.url=jdbc:clickhouse://clickhouse:8123/default \
  --conf spark.sql.catalog.clickhouse.user=admin \
  --conf spark.sql.catalog.clickhouse.password=admin \
  --conf spark.sql.catalog.clickhouse.driver=com.clickhouse.jdbc.ClickHouseDriver \
  --conf spark.sql.catalog.clickhouse.pushDownPredicate=true \
  --conf spark.sql.catalog.clickhouse.pushDownAggregate=true \
  --conf spark.sql.catalog.clickhouse.pushDownLimit=true

echo "=== Waiting for Thrift Server to be ready ==="
sleep 15

# Check if Thrift Server is running
if netstat -tuln | grep 10000; then
    echo "✓ Spark Thrift Server is running on port 10000"
else
    echo "⚠ WARNING: Thrift Server may not be running on port 10000"
    echo "Checking processes..."
    ps aux | grep -i thrift || true
fi

echo "=== Checking for Ranger initialization in logs ==="
sleep 5
if ls /opt/bitnami/spark/logs/*.out 1> /dev/null 2>&1; then
    echo "Searching for Ranger messages..."
    grep -i "ranger" /opt/bitnami/spark/logs/*.out 2>/dev/null | head -20 || echo "No Ranger messages found yet"
fi

echo ""
echo "=== Tailing logs ==="
if ls /opt/bitnami/spark/logs/*.out 1> /dev/null 2>&1; then
    tail -f /opt/bitnami/spark/logs/*.out
else
    echo "⚠ No log files found yet. Waiting..."
    sleep 10
    tail -f /opt/bitnami/spark/logs/*.out
fi
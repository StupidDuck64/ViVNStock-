#!/bin/bash
# VNStock 1m backfill — 900 days via VCI direct API
# All JARs and args are explicit (no shell variable issues)

export DNSE_API_KEY='eyJvcmciOiJkbnNlIiwiaWQiOiI3M2JlOGU3MzFhZWQ0MTFkODA5ODYxZDRiN2IxZWM4YSIsImgiOiJtdXJtdXIxMjgifQ=='

echo "=== BACKFILL_1M_900D_VCI START: $(date) ==="

/opt/bitnami/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode client \
  --driver-memory 600M \
  --executor-memory 3G \
  --executor-cores 4 \
  --num-executors 2 \
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
  --conf spark.sql.catalog.iceberg=org.apache.iceberg.spark.SparkCatalog \
  --conf spark.sql.catalog.iceberg.type=hive \
  --conf spark.sql.catalog.iceberg.uri=thrift://hive-metastore:9083 \
  --conf spark.sql.catalog.iceberg.warehouse=s3a://iceberg/warehouse \
  --conf spark.sql.catalog.iceberg.io-impl=org.apache.iceberg.aws.s3.S3FileIO \
  --conf spark.sql.catalog.iceberg.s3.endpoint=http://minio:9000 \
  --conf "spark.sql.catalog.iceberg.s3.path-style-access=true" \
  --conf spark.sql.catalog.iceberg.s3.access-key-id=minio \
  --conf spark.sql.catalog.iceberg.s3.secret-access-key=minio123 \
  --conf spark.sql.catalog.iceberg.s3.region=us-east-1 \
  --conf spark.hadoop.fs.s3a.endpoint=http://minio:9000 \
  --conf "spark.hadoop.fs.s3a.path.style.access=true" \
  --conf "spark.hadoop.fs.s3a.connection.ssl.enabled=false" \
  --conf spark.hadoop.fs.s3a.aws.credentials.provider=org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider \
  --conf spark.hadoop.fs.s3a.access.key=minio \
  --conf spark.hadoop.fs.s3a.secret.key=minio123 \
  --conf spark.sql.defaultCatalog=iceberg \
  --conf spark.sql.adaptive.enabled=true \
  --jars /opt/bitnami/spark/jars/iceberg-spark-runtime-3.5_2.12-1.9.2.jar,/opt/bitnami/spark/jars/iceberg-aws-bundle-1.9.2.jar,/opt/bitnami/spark/jars/hadoop-aws-3.3.4.jar,/opt/bitnami/spark/jars/aws-java-sdk-bundle-1.12.791.jar \
  /opt/spark/jobs/vnstock/backfill_1m.py \
  --symbols-file /opt/spark/jobs/vnstock/symbols.txt \
  --days 900 \
  --workers 5 \
  --batch-size 5 \
  --mode overwrite

echo "=== EXIT=$? END: $(date) ==="

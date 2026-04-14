# ============================================================
# morning_startup.ps1 — VVS Dashboard: Khởi động buổi sáng
# Chạy trước khi thị trường mở (trước 9:00 VN)
# Cách dùng: .\morning_startup.ps1
# ============================================================

Set-Location "d:\Azriel\Source_code\2026\lakehouse-oss-vuong.ngo"

Write-Host "`n[1/5] Khởi động toàn bộ infrastructure (core + vnstock)..." -ForegroundColor Cyan
docker compose --profile core --profile vnstock up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: docker compose up thất bại!" -ForegroundColor Red
    exit 1
}

Write-Host "`n[2/5] Chờ Redis healthy..." -ForegroundColor Cyan
$timeout = 60
$elapsed = 0
do {
    Start-Sleep -Seconds 3
    $elapsed += 3
    $state = docker inspect --format "{{.State.Health.Status}}" lakehouse-oss-vuongngo-redis-1 2>$null
} while ($state -ne "healthy" -and $elapsed -lt $timeout)

if ($state -ne "healthy") {
    Write-Host "WARNING: Redis chưa healthy sau ${timeout}s, tiếp tục..." -ForegroundColor Yellow
} else {
    Write-Host "  Redis: healthy" -ForegroundColor Green
}

Write-Host "`n[3/5] Chờ Producer xác thực WebSocket DNSE..." -ForegroundColor Cyan
$elapsed = 0
do {
    Start-Sleep -Seconds 3
    $elapsed += 3
    $log = docker logs lakehouse-oss-vuongngo-vnstock-producer-1 --since 30s 2>&1 | Out-String
} while ($log -notmatch "Session ID:" -and $elapsed -lt 90)

if ($log -match "Session ID:") {
    Write-Host "  Producer: WebSocket connected" -ForegroundColor Green
} else {
    Write-Host "WARNING: Producer chưa kết nối sau ${elapsed}s" -ForegroundColor Yellow
    Write-Host "  Thử restart producer..." -ForegroundColor Yellow
    docker restart lakehouse-oss-vuongngo-vnstock-producer-1
    Start-Sleep -Seconds 10
}

Write-Host "`n[4/5] Kiểm tra giá realtime VCB & HPG..." -ForegroundColor Cyan
Start-Sleep -Seconds 5
try {
    $vcb = Invoke-RestMethod "http://localhost:8060/api/realtime/summary?symbol=VCB"
    $hpg = Invoke-RestMethod "http://localhost:8060/api/realtime/summary?symbol=HPG"
    $vcbClose = $vcb.tick.close
    $vcbPct = $vcb.daily.changePct
    $hpgClose = $hpg.tick.close
    $hpgPct = $hpg.daily.changePct
    Write-Host "  VCB: $vcbClose  ($vcbPct%)" -ForegroundColor Green
    Write-Host "  HPG: $hpgClose  ($hpgPct%)" -ForegroundColor Green
} catch {
    Write-Host "  API chưa sẵn sàng, chờ thêm 10s..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
}

Write-Host "`n[5/5] Backfill nến 1M hôm nay từ DNSE → Iceberg (Spark)..." -ForegroundColor Cyan
Write-Host "  (chạy sau 9:30 để có đủ nến đầu phiên)" -ForegroundColor DarkGray

$sparkCmd = @(
    "docker", "exec", "lakehouse-oss-vuongngo-spark-master-1",
    "/opt/bitnami/spark/bin/spark-submit",
    "--master", "spark://spark-master:7077",
    "--deploy-mode", "client",
    "--conf", "spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
    "--conf", "spark.sql.catalog.iceberg=org.apache.iceberg.spark.SparkCatalog",
    "--conf", "spark.sql.catalog.iceberg.type=hive",
    "--conf", "spark.sql.catalog.iceberg.uri=thrift://hive-metastore:9083",
    "--conf", "spark.sql.catalog.iceberg.warehouse=s3a://iceberg/warehouse",
    "--conf", "spark.sql.catalog.iceberg.io-impl=org.apache.iceberg.aws.s3.S3FileIO",
    "--conf", "spark.sql.catalog.iceberg.s3.endpoint=http://minio:9000",
    "--conf", "spark.sql.catalog.iceberg.s3.path-style-access=true",
    "--conf", "spark.sql.catalog.iceberg.s3.region=us-east-1",
    "--conf", "spark.hadoop.fs.s3a.endpoint=http://minio:9000",
    "--conf", "spark.hadoop.fs.s3a.path.style.access=true",
    "--conf", "spark.hadoop.fs.s3a.connection.ssl.enabled=false",
    "--conf", "spark.hadoop.fs.s3a.aws.credentials.provider=org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
    "--conf", "spark.hadoop.fs.s3a.access.key=minio",
    "--conf", "spark.hadoop.fs.s3a.secret.key=minio123",
    "--conf", "spark.sql.defaultCatalog=iceberg",
    "--conf", "spark.executor.memory=2G",
    "--conf", "spark.executor.instances=2",
    "--jars", "/opt/bitnami/spark/jars/iceberg-spark-runtime-3.5_2.12-1.9.2.jar,/opt/bitnami/spark/jars/iceberg-aws-bundle-1.9.2.jar,/opt/bitnami/spark/jars/hadoop-aws-3.3.4.jar,/opt/bitnami/spark/jars/aws-java-sdk-bundle-1.12.791.jar",
    "/opt/spark/jobs/vnstock/backfill_1m.py",
    "--symbols-file", "/tmp/all_symbols.txt",
    "--days", "1",
    "--run-mode", "daily"
)

& $sparkCmd[0] $sparkCmd[1..($sparkCmd.Length-1)] 2>&1 | Select-Object -Last 5

Write-Host "`n=============================" -ForegroundColor Cyan
Write-Host " VVS Dashboard sẵn sàng!" -ForegroundColor Green
Write-Host " Frontend:  http://localhost:3080" -ForegroundColor White
Write-Host " API docs:  http://localhost:8060/docs" -ForegroundColor White
Write-Host "=============================" -ForegroundColor Cyan

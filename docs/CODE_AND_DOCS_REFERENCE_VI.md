# 🗺️ Bản Đồ Code & Tài Liệu - VNStock Data Lakehouse

**Cập nhật**: 07/04/2026  
**Mục đích**: Hướng dẫn nhanh để theo dõi tất cả streaming pipelines, jobs, DAGs và tài liệu liên quan

---

## 📚 Tài Liệu Hệ Thống (Đọc Trước Tiên)

| Tài Liệu | Nội Dung | Khi Nào Đọc |
|---------|---------|------------|
| [docs/SYSTEM_EXPLANATION_VI.md](SYSTEM_EXPLANATION_VI.md) | **Toàn bộ kiến trúc hệ thống (Vietnamese, ~1000 words)** - Bắt đầu từ đây | 🔴 Đọc đầu tiên |
| [docs/VNSTOCK_PIPELINE_VI.md](VNSTOCK_PIPELINE_VI.md) | **Chi tiết VNStock pipeline (Non-technical)** - Giải thích cho người không code | Hiểu flow chính |
| [docs/architecture.md](architecture.md) | Diagram & UML, thành phần chính | Xem cấu trúc tổng quan |
| [docs/development.md](development.md) | Hướng dẫn setup dev environment | Chạy local |
| [docs/troubleshooting.md](troubleshooting.md) | Lỗi thường gặp & cách fix | Khi có vấn đề |

---

## 🔀 Streaming Pipelines & Linear Processing

### 1️⃣ **VNStock Backfill 1D** (Daily Historical Data)
> **Mục đích**: Fetch daily OHLCV từ DNSE REST API, ghi vào Bronze layer  
> **Tần suất**: Daily 02:00 ICT (incremental append mode)

**Tài liệu liên quan**:
- 📖 [docs/VNSTOCK_PIPELINE_VI.md](VNSTOCK_PIPELINE_VI.md) - Phần "1D Daily"

**Files code cần đọc**:
```
1. Spark Job (Thực tế fetch & xử lý):
   infra/airflow/processing/spark/jobs/vnstock/backfill_1d.py
   ├─ parse_args()              # Parse CLI arguments
   ├─ main()                    # HWM query, resolve run_mode init/daily
   ├─ fetch_dnse_daily()        # HTTP fetch từ DNSE
   ├─ _fetch_one(sym)           # Per-symbol fetch (parallel)
   └─ _write_batch()            # Ghi vào Iceberg (append/replace)

2. Airflow DAG (Orchestration):
   infra/airflow/dags/vnstock_backfill_dag.py
   └─ DAG: vnstock_backfill_1d_weekly
      ├─ check_api_key          # Validate DNSE_API_KEY
      ├─ run_backfill_1d        # SparkSubmitOperator
      └─ maintenance_1d         # Iceberg snapshot cleanup

3. Shared Utilities:
   infra/airflow/processing/spark/jobs/spark_utils.py
   └─ Spark config, ENV vars, paths
```

**Run modes**:
- `--run-mode init`: Full `createOrReplace` (manual backfill)
- `--run-mode daily`: Append with high-water mark (scheduled)

**Output tables**:
- `iceberg.bronze.vnstock_ohlc_1d` (6.3M+ rows)

---

### 2️⃣ **VNStock Backfill 1M** (Minute-Level Data + Aggregations)
> **Mục đích**: Fetch 1M data từ VCI, auto-aggregate 5m/15m/30m/1h/4h  
> **Tần suất**: Daily 01:00 ICT (incremental append mode)

**Tài liệu liên quan**:
- 📖 [docs/VNSTOCK_PIPELINE_VI.md](VNSTOCK_PIPELINE_VI.md) - Phần "1M Intraday"

**Files code cần đọc**:
```
1. Spark Job (Fetch + Aggregate):
   infra/airflow/processing/spark/jobs/vnstock/backfill_1m.py
   ├─ parse_args()              # --run-mode init/daily, --days N
   ├─ main()                    # HWM query, per-symbol from_ts
   ├─ _fetch_one(sym)           # VCI API + DNSE fallback
   ├─ _write_batch()            # Append/replace to 1m
   ├─ _aggregate_5m/15m/30m()   # CreateOrReplace aggregations
   ├─ _aggregate_1h/4h()        # Re-aggregate từ full 1m table
   └─ Spark config              # partitionOverwriteMode=dynamic

2. Airflow DAG:
   infra/airflow/dags/vnstock_backfill_dag.py
   └─ DAG: vnstock_backfill_1m_daily
      ├─ check_api_key
      ├─ run_backfill_1m        # --run-mode daily --days 3
      └─ maintenance_1m         # Cleanup

3. Shared:
   infra/airflow/processing/spark/jobs/spark_utils.py
```

**High-Water Mark (HWM)**: Nếu `--run-mode daily`, query `MAX(time)` per symbol từ Iceberg, fetch từ đó trở lên (không refetch cũ)

**Output tables**:
- `iceberg.bronze.vnstock_ohlc_1m` (6.3M+ rows)
- `iceberg.bronze.vnstock_ohlc_5m` (1.3M+ rows, derived)
- `iceberg.bronze.vnstock_ohlc_15m` (430K+ rows, derived)
- `iceberg.bronze.vnstock_ohlc_30m` (215K+ rows, derived)
- `iceberg.bronze.vnstock_ohlc_1h` (107K+ rows, derived)
- `iceberg.bronze.vnstock_ohlc_4h` (27K+ rows, derived)

---

### 3️⃣ **VNStock Hybrid Producer** (Real-Time Speed Layer + Batch Layer)
> **Mục đích**: Kiến trúc Hybrid gồm 2 luồng chạy song song trong 1 container  
> **Cập nhật**: 07/04/2026

**Tài liệu liên quan**:
- 📖 [docs/SYSTEM_EXPLANATION_VI.md](SYSTEM_EXPLANATION_VI.md) - Phần "Kiến Trúc Hybrid Producer"

**Files code cần đọc**:
```
1. Hybrid Producer (Điểm vào chính):
   infra/vnstock/producer.py
   ├─ ws_speed_layer()       # Speed Layer: WS → Redis + Kafka (tick-by-tick)
   ├─   ├─ on_trade()         # Khớp lệnh → build live 1m candle in-memory
   ├─   ├─ on_ohlc_1m()       # Server-confirmed 1m candle → ghi đè live
   ├─   ├─ on_ohlc_1d()       # Daily candle → Redis daily
   ├─   ├─ on_secdef()        # Giá tham chiếu, trần, sàn
   ├─   └─ on_quote()         # Bid/ask depth
   ├─ rest_batch_layer()     # Batch Layer: REST mỗi 60s → Kafka → Iceberg
   ├─   ├─ _fetch_finalized_candle()  # Lấy nến đã chốt (index -2)
   ├─   └─ _fetch_daily()     # Daily secdef fallback (mỗi 5 phút)
   └─ main()                 # asyncio.gather: WS + REST + stats

2. WebSocket SDK (local package):
   infra/vnstock/trading_websocket/
   ├─ client.py              # TradingClient: HMAC auth, subscribe, dispatch
   ├─ connection.py          # WebSocketConnection: extra_headers (Origin + Bearer)
   ├─ auth.py                # HMAC-SHA256 signature generation
   ├─ models.py              # Trade, Ohlc, SecurityDefinition, Quote dataclasses
   └─ encoding.py            # JSON / msgpack encoder-decoder

3. FastAPI WebSocket (200ms poll):
   infra/vnstock-api/app/routers/ws.py
   └─ POLL_INTERVAL = 0.2    # Tăng từ 500ms → 200ms cho Speed Layer
```

**Key design decisions**:
- DNSE WS handshake cần `Origin: https://trading.dnse.com.vn` (đã fix)
- `_live_candles` dict: build 1m candle từ từng trade tick (bucket by minute)
- `on_ohlc_1m` ghi đè live candle khi server gửi confirmed OHLC (authoritative)
- Batch Layer lấy index `-2` (nến đã đóng), không phải `-1` (đang hình thành)
- aiokafka dùng `gzip` (lý do: lz4 module không đủ native binary trong Alpine Python)

---

### 4️⃣ **Silver Layer - Dimensional & Fact Tables** (Scheduled Transform)
> **Mục đích**: Clean + reshape Bronze → Silver (Retail Star Schema)  
> **Tần suất**: Nightly 03:00 ICT (batch)

**Tài liệu liên quan**:
- 📖 [docs/VNSTOCK_PIPELINE_VI.md](VNSTOCK_PIPELINE_VI.md) - Phần "Silver Layer"

**Files code cần đọc**:
```
1. Silver Service (Orchestrate builders):
   infra/airflow/processing/spark/jobs/silver/silver_retail_service.py
   ├─ parse_args()              # --selection (which tables)
   ├─ main()                    # Resolve table builders, materialize
   ├─ materialise_tables()      # Execute builders by dependency order
   └─ enforce_primary_key()     # Uniqueness constraint

2. Table Builders (Mỗi table một file):
   infra/airflow/processing/spark/jobs/silver/builders/
   ├─ dim_customer_profile.py   # SCD2 customer dimension
   ├─ dim_date.py               # Date dimension (pre-generated)
   ├─ dim_product_catalog.py    # Product master data
   ├─ dim_supplier.py           # Supplier master
   ├─ dim_warehouse.py          # Warehouse master
   ├─ fact_customer_engagement.py  # Events fact table
   ├─ fact_inventory_position.py   # Inventory snapshot fact
   └─ fact_order_service.py     # Order fact table

3. Shared Silver Utils:
   infra/airflow/processing/spark/jobs/silver/common.py
   ├─ with_payload()            # Decode complex fields
   ├─ parse_bronze_topic()      # Normalize column names
   ├─ parse_cdc_table()         # Extract CDC metadata
   ├─ unix_ms_to_ts()           # Timestamp conversion
   ├─ scd2_from_events()        # SCD2 logic
   └─ surrogate_key()           # Generate SK

4. Builder Registry:
   infra/airflow/processing/spark/jobs/silver/registry.py
   └─ BUILDER_MAP               # Define order & deps

5. Airflow DAG:
   infra/airflow/dags/silver_retail_star_schema_dag.py
   └─ DAG: silver_retail_star_schema_nightly
      ├─ check_bronze_ready     # Validate sources
      ├─ build_dimensions       # Dim builders
      ├─ build_facts             # Fact builders
      └─ validate_counts        # Quality check

6. Shared:
   infra/airflow/processing/spark/jobs/spark_utils.py
```

**Output tables** (Silver layer):
- `iceberg.silver.dim_*` (6 dimension tables)
- `iceberg.silver.fact_*` (3 fact tables)

---

### 5️⃣ **Additional Jobs & Utilities**

#### **VNStock Dedup Job** (Data Quality)
- **Purpose**: Remove duplicate 1m candles within same minute bucket
- **File**: `infra/airflow/processing/spark/jobs/vnstock/dedup_1m.py`
- **Frequency**: Post-backfill or ad-hoc
- **Triggers**: Manual or as dependency after backfill

#### **VNStock News Crawler** (News Ingestion)
- **Purpose**: Scrape financial news, store in Iceberg
- **File**: `infra/airflow/processing/spark/jobs/vnstock/news_crawler.py`
- **Frequency**: Multiple times daily
- **DAG**: `infra/airflow/dags/vnstock_backfill_news_dag.py`

#### **VNStock Compact Job** (Iceberg Maintenance)
- **Purpose**: Compact small Parquet files → fewer larger files
- **File**: `infra/airflow/processing/spark/jobs/vnstock/compact.py`
- **Frequency**: Weekly or after heavy writes

#### **DAG Sync Manager** (Sync mechanism)
- **Purpose**: Watch S3→MinIO for DAG changes, auto-reload
- **File**: `infra/airflow/dags/dag_sync_manager.py`
- **Runs**: 24/7 polling

---

## 📊 Data Flow Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA SOURCES                                  │
├─────────────────────────────────────────────────────────────────┤
│ VCI (WebSocket)  │  DNSE REST API  │  WebSocket Events  │ News   │
└────────┬──────────┴────────┬────────┴────────┬──────────┴────┬───┘
         │                   │                 │               │
    ┌────▼──────┐   ┌───────▼────┐      ┌─────▼──────┐   ┌────▼──────┐
    │ backfill  │   │  backfill  │      │   Kafka    │   │   News    │
    │   1m.py   │   │   1d.py    │      │  Streaming │   │ Crawler   │
    │           │   │            │      │  Events    │   │           │
    └────┬──────┘   └───────┬────┘      └─────┬──────┘   └────┬──────┘
         │ (HWM)           │ (HWM)           │ (streaming)    │
         │                 │                 │                │
    ┌────▼────────────────▼────────────────▼────────────┬───▼────────┐
    │       BRONZE LAYER (Iceberg Tables)              │            │
    │  ┌─────────────────────────────────────────┐     │            │
    │  │ vnstock_ohlc_1m   (6.3M rows)          │     │ vnstock    │
    │  │ vnstock_ohlc_1d   (6.3M rows)          │     │ news       │
    │  │ vnstock_ohlc_5m   (1.3M rows, derived) │     │            │
    │  │ vnstock_ohlc_15m  (430K rows, derived) │     │            │
    │  │ vnstock_ohlc_30m  (215K rows, derived) │     │            │
    │  │ vnstock_ohlc_1h   (107K rows, derived) │     │            │
    │  │ vnstock_ohlc_4h   (27K rows, derived)  │     │            │
    │  │ vnstock_depth     (streaming CDC)      │     │            │
    │  │ vnstock_kline     (streaming CDC)      │     │            │
    │  └─────────────────────────────────────────┘     │            │
    └────┬──────────────────────────────────────────────┴───┬────────┘
         │                                                  │
         ├─ Dedup 1m ──┐                                   │
         │             │                                   │
    ┌────▼─────────────▼──────────────────────────────────▼────────┐
    │       SILVER LAYER (Iceberg Tables)                         │
    │  ┌────────────────────────────────────────────────────┐     │
    │  │ Dimensions:                                        │     │
    │  │  • dim_customer_profile   (SCD2)                  │     │
    │  │  • dim_date                                        │     │
    │  │  • dim_product_catalog                             │     │
    │  │  • dim_supplier                                    │     │
    │  │  • dim_warehouse                                   │     │
    │  │                                                    │     │
    │  │ Facts:                                             │     │
    │  │  • fact_customer_engagement                        │     │
    │  │  • fact_inventory_position                         │     │
    │  │  • fact_order_service                              │     │
    │  └────────────────────────────────────────────────────┘     │
    └─────────────────────────────────────────────────────────────┘
         │
         └─► FastAPI (Serving Layer)
             ├─ /api/history (Time series query)
             ├─ /api/candles (Multi-symbol fetch)
             └─ [Redis caching]
```

---

## 🔍 Cheat Sheet: "Tôi muốn sửa/hiểu..."

| Yêu cầu | Files cần đọc | Dòng code chính |
|--------|---------------|----------------|
| Hiểu kiến trúc hệ thống | [SYSTEM_EXPLANATION_VI.md](SYSTEM_EXPLANATION_VI.md) | Phần Hybrid Producer |
| Sửa Speed Layer WS | `infra/vnstock/producer.py` | `ws_speed_layer()`, `on_trade()` |
| Sửa Batch Layer REST | `infra/vnstock/producer.py` | `rest_batch_layer()`, `_fetch_finalized_candle()` |
| Sửa WS SDK (auth/headers) | `infra/vnstock/trading_websocket/client.py`, `connection.py` | `extra_headers`, `_authenticate()` |
| Sửa logic fetch 1D data | `backfill_1d.py` | `fetch_dnse_daily()` |
| Sửa logic fetch 1M data | `backfill_1m.py` | `_fetch_one()` |
| Thay đổi HWM strategy | `backfill_1m.py` + `backfill_1d.py` | Dòng 220-250 (HWM query) |
| Thêm aggregation mới | `backfill_1m.py` | `_aggregate_*()` functions |
| Sửa timezone chart | `infra/vnstock-frontend/src/services/api.js` | `VN_OFFSET = 7 * 3600` |
| Sửa heatmap changePct | `infra/vnstock-frontend/src/components/SectorHeatmap.js` | `liveClose` calculation |
| Tăng tốc độ WS frontend | `infra/vnstock-api/app/routers/ws.py` | `POLL_INTERVAL` |
| Thay đổi schedule | `infra/airflow/dags/*.py` | `schedule="..."` |
| Điều chỉnh parallelism | `spark_utils.py` + DAG files | `--executor-instances`, `workers` |
| Hiểu toàn bộ flow | 1. [SYSTEM_EXPLANATION_VI.md](SYSTEM_EXPLANATION_VI.md) → 2. [VNSTOCK_PIPELINE_VI.md](VNSTOCK_PIPELINE_VI.md) → 3. Individual job files |

---

## 📂 File Structure Overview

```
lakehouse-oss-vuong.ngo/
├── docs/                    (Tài liệu)
│   ├── SYSTEM_EXPLANATION_VI.md   ⭐ Đọc trước (Kiến trúc Hybrid Producer)
│   ├── VNSTOCK_PIPELINE_VI.md     ⭐ Pipeline overview (non-technical)
│   ├── CODE_AND_DOCS_REFERENCE_VI.md  ⭐ Bản này (bản đồ file)
│   ├── architecture.md
│   ├── development.md
│   └── troubleshooting.md
│
├── infra/vnstock/           (Hybrid Producer)
│   ├── producer.py            ⭐ MAIN: asyncio hybrid (Speed WS + Batch REST)
│   ├── producer_ws.py         (legacy WS-only, deprecated)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── trading_websocket/     (DNSE WS SDK, local package)
│       ├── client.py           ⭐ TradingClient (connect, auth, subscribe)
│       ├── connection.py       ⭐ WebSocketConnection + extra_headers fix
│       ├── auth.py             HMAC-SHA256 signature
│       ├── models.py           Trade, Ohlc, SecurityDefinition, Quote
│       └── encoding.py         JSON / msgpack
│
├── infra/vnstock-api/       (FastAPI Backend)
│   └── app/
│       ├── main.py             CORS, GZip, lifespan (Redis + Trino init)
│       ├── connections.py      Async Redis pool, Trino retry
│       └── routers/
│           ├── ws.py           ⭐ WebSocket /api/ws/stream (200ms poll)
│           ├── history.py      /api/history → Trino → Iceberg
│           ├── realtime.py     /api/realtime → Redis
│           ├── symbols.py      /api/symbols
│           └── news.py         /api/news
│
├── infra/vnstock-frontend/  (React Frontend)
│   └── src/
│       ├── services/
│       │   └── api.js          ⭐ WebSocket client, VN_OFFSET +7h, history fetch
│       └── components/
│           ├── CandlestickChart.js  ⭐ TradingView-style, 20+ indicators, live candle
│           ├── SectorHeatmap.js     ⭐ Dual treemap (gain/loss), live changePct
│           └── IndicatorPanel.js    Dropdown toggle 20+ indicators
│
├── infra/airflow/           (Airflow + Spark Jobs)
│   ├── dags/
│   │   ├── vnstock_backfill_dag.py    (1D daily + 1M daily schedule)
│   │   ├── silver_retail_star_schema_dag.py
│   │   └── dag_sync_manager.py
│   └── processing/spark/jobs/
│       ├── vnstock/
│       │   ├── backfill_1m.py         Fetch DNSE 1m → Iceberg (HWM mode)
│       │   ├── backfill_1d.py         Fetch DNSE 1D → Iceberg (HWM mode)
│       │   ├── dedup_1m.py            Remove duplicate candles
│       │   └── news_crawler.py        Crawl financial news → Iceberg
│       ├── silver/                Star schema builders
│       └── spark_utils.py         Spark session config, env vars
│
└── docker-compose.yml       (13 containers — profiles: vnstock, core)
```

---

## 🚀 Quick Command Reference

```powershell
# Kiểm tra hệ thống
docker ps --format "table {{.Names}}\t{{.Status}}"

# Xem log Producer (Speed Layer WS + Batch Layer REST)
docker logs --tail 20 lakehouse-oss-vuongngo-vnstock-producer-1

# Rebuild + deploy Producer
Push-Location d:\Azriel\Source_code\2026\lakehouse-oss-vuong.ngo
docker compose up -d --build vnstock-producer
Pop-Location

# Backfill 1m — chạy cho tất cả symbols hôm nay
docker exec lakehouse-oss-vuongngo-spark-master-1 /opt/bitnami/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --conf "spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions" \
  --conf "spark.sql.catalog.iceberg=org.apache.iceberg.spark.SparkCatalog" \
  --conf "spark.sql.catalog.iceberg.type=hive" \
  --conf "spark.sql.catalog.iceberg.uri=thrift://hive-metastore:9083" \
  --conf "spark.sql.catalog.iceberg.warehouse=s3a://iceberg/warehouse" \
  --conf "spark.sql.catalog.iceberg.io-impl=org.apache.iceberg.aws.s3.S3FileIO" \
  --conf "spark.sql.catalog.iceberg.s3.endpoint=http://minio:9000" \
  --conf "spark.sql.catalog.iceberg.s3.path-style-access=true" \
  --conf "spark.sql.catalog.iceberg.s3.region=us-east-1" \
  --conf "spark.hadoop.fs.s3a.endpoint=http://minio:9000" \
  --conf "spark.hadoop.fs.s3a.path.style.access=true" \
  --conf "spark.hadoop.fs.s3a.connection.ssl.enabled=false" \
  --conf "spark.hadoop.fs.s3a.aws.credentials.provider=org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider" \
  --conf "spark.hadoop.fs.s3a.access.key=minio" \
  --conf "spark.hadoop.fs.s3a.secret.key=minio123" \
  --conf "spark.sql.defaultCatalog=iceberg" \
  --conf "spark.executor.memory=2G" \
  --conf "spark.executor.instances=2" \
  --jars "/opt/bitnami/spark/jars/iceberg-spark-runtime-3.5_2.12-1.9.2.jar,/opt/bitnami/spark/jars/iceberg-aws-bundle-1.9.2.jar,/opt/bitnami/spark/jars/hadoop-aws-3.3.4.jar,/opt/bitnami/spark/jars/aws-java-sdk-bundle-1.12.791.jar" \
  /opt/spark/jobs/vnstock/backfill_1m.py \
  --symbols-file /tmp/all_symbols.txt \
  --days 1 --run-mode daily

# Rebuild frontend
Push-Location d:\Azriel\Source_code\2026\lakehouse-oss-vuong.ngo
docker compose up -d --build vnstock-frontend
Pop-Location

# Test realtime API
curl http://localhost:8060/api/realtime?symbol=VCB

# Test history API
curl "http://localhost:8060/api/history?symbol=VCB&interval=1m&limit=10"
```

---

## 📌 Các Điểm Quan Trọng

✅ **HWM (High-Water Mark)**: Mỗi job daily mode query `MAX(time)` per symbol từ Iceberg, chỉ fetch data mới từ đó trở lên

✅ **Run Modes**: `--run-mode init` (full replace) vs `--run-mode daily` (append chỉ với new data)

✅ **Aggregations**: 1m → 5m/15m/30m/1h/4h được re-aggregate từ **full 1m table** mỗi lần, không incremental (đảm bảo boundary buckets đúng)

✅ **Iceberg**: Tất cả Bronze + Silver tables dùng Iceberg table format v2, hỗ trợ ACID + time travel

✅ **Streaming**: Kafka topics act as buffers, Spark Streaming xử lý micro-batches → Iceberg append

---

**Bắt đầu**: Đọc [SYSTEM_EXPLANATION_VI.md](SYSTEM_EXPLANATION_VI.md) xong rồi tới [VNSTOCK_PIPELINE_VI.md](VNSTOCK_PIPELINE_VI.md) để get overview toàn bộ. Sau đó dive vào code theo bảng "Cheat Sheet" phía trên.

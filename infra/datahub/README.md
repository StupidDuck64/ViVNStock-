# 🏷️ DataHub — Nền Tảng Quản Lý Metadata

[DataHub](https://datahubproject.io/) là một nền tảng metadata mã nguồn mở để khám phá, hiểu rõ và quản lý dữ liệu trên toàn bộ tổ chức.

---

## 📋 Mục Lục

1. [Tổng Quan](#tổng-quan)
2. [Kiến Trúc](#kiến-trúc)
3. [Các Thành Phần](#các-thành-phần)
4. [Cấu Hình](#cấu-hình)
5. [Bắt Đầu](#bắt-đầu)
6. [Cách Sử Dụng](#cách-sử-dụng)
7. [Biến Môi Trường](#biến-môi-trường)
8. [Khắc Phục Sự Cố](#khắc-phục-sự-cố)
9. [Tài Nguyên](#tài-nguyên)

---

## Tổng Quan

### Tại Sao Sử Dụng DataHub?

DataHub cho phép:
- **Khám Phá Metadata**: Tìm datasets, pipelines, schemas trên toàn nền tảng
- **Dòng Chảy Dữ Liệu (Lineage)**: Hiểu dòng chảy dữ liệu và các phụ thuộc
- **Quản Lý Dữ Liệu**: Kiểm soát truy cập, quyền sở hữu, tuân thủ
- **Tích Hợp**: Hoạt động với Kafka, Spark, Trino, Airflow, và nhiều hệ thống khác
- **Nhập Dữ Liệu**: Tự động khám phá technical metadata từ các sources khác nhau

### Cách Hoạt Động

DataHub sử dụng **kiến trúc hướng metadata**:
1. **Kafka** ghi lại metadata events theo thời gian thực
2. **Elasticsearch** lập chỉ mục metadata có thể tìm kiếm
3. **Neo4j** lưu trữ entity relationships và lineage
4. **PostgreSQL** duy trì persistent state
5. **Frontend React** cung cấp giao diện tương tác

---

## Kiến Trúc

### Profile: `datahub`

Bật bằng:
```bash
docker compose --profile datahub up -d
```

### Sơ Đồ Thành Phần

```
┌─────────────────────────────────────────────────────────┐
│                    DataHub Platform                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Frontend    │  │  GMS         │  │  Actions     │  │
│  │  React UI    │  │  (API)       │  │  (Events)    │  │
│  │  :9002       │  │  :8080       │  │              │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                  │          │
│         └─────────────────┼──────────────────┘          │
│                           │                             │
├─────────────────────────────────────────────────────────┤
│           Metadata & Event Infrastructure               │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Elasticsearch│  │ Neo4j Graph  │  │ PostgreSQL   │  │
│  │ (Search)     │  │ (Lineage)    │  │ (State)      │  │
│  │ :9200        │  │ :7474, :7687 │  │ port 5432    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
├─────────────────────────────────────────────────────────┤
│              Message Queue & Schemas                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Kafka        │  │ Schema       │  │ Ingestion    │  │
│  │ (Events)     │  │ Registry     │  │ (Pipelines)  │  │
│  │ :29092       │  │ :8081        │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Các Thành Phần

### 1. **datahub-gms** (Generalized Metadata Service)

**Port:** `8080` (ánh xạ via `DATAHUB_MAPPED_GMS_PORT`)

**Mục Đích:** Core API server cho metadata operations
- RESTful API để CRUD operations trên entities
- Xử lý metadata events theo thời gian thực
- Quản lý authorization và authentication

**Biến Môi Trường Chính:**
- `DATAHUB_SERVER_TYPE`: `quickstart` (mặc định)
- `EBEAN_DATASOURCE_URL`: Kết nối PostgreSQL
- `ELASTICSEARCH_HOST`: Elasticsearch cluster
- `KAFKA_BOOTSTRAP_SERVER`: Kafka broker

**Phụ Thuộc:**
- PostgreSQL (metadata storage)
- Elasticsearch (full-text search)
- Kafka (event streaming)
- Neo4j (graph database)
- datahub-upgrade (phải hoàn tất trước)

**Health Check:**
```bash
curl -sS --fail http://localhost:8080/health
```

---

### 2. **datahub-frontend-react**

**Port:** `9002` (ánh xạ via `DATAHUB_MAPPED_FRONTEND_PORT`)

**Mục Đích:** Giao diện web tương tác để khám phá metadata
- Tìm kiếm và duyệt datasets
- Xem lineage và impact analysis
- Quản lý ownership và tài liệu
- Xử lý advanced filtering

**Biến Môi Trường Chính:**
- `DATAHUB_GMS_HOST` / `DATAHUB_GMS_PORT`: Kết nối GMS
- `DATAHUB_SECRET`: Session secret
- `ELASTIC_CLIENT_HOST`: Elasticsearch cho search

**Phụ Thuộc:**
- datahub-gms (phải healthy)

---

### 3. **datahub-ingestion**

**Mục Đích:** Chạy metadata ingestion pipelines từ sources bên ngoài
- Khám phá metadata từ Postgres, Kafka, Spark, etc.
- Áp dụng YAML-based ingestion recipes
- Đẩy metadata tới GMS qua REST API

**Vị Trí Recipe:**
```
./infra/datahub/ingestion/recipes/
```

**Hỗ Trợ Tích Hợp:**
- PostgreSQL (via SQL lineage)
- Kafka (topics, schemas)
- Schema Registry (Avro/Protobuf)
- Apache Spark (Thrift Server)
- Và nhiều hệ thống khác...

**Cấu Trúc Ví Dụ Recipe:**
```yaml
source:
  type: postgres
  config:
    host_port: postgres:5432
    database: demo
    username: admin
    password: admin

sink:
  type: datahub-rest
  config:
    server: http://datahub-gms:8080

transformers:
  - type: add_dataset_ownership
    config:
      owner_type: "DATAOWNER"
```

---

### 4. **datahub-actions**

**Mục Đích:** Xử lý metadata events và kích hoạt hành động
- Phản ứng với metadata change events
- Có thể thông báo cho các hệ thống bên ngoài
- Thực hiện business logic tùy chỉnh

**Biến Môi Trường Chính:**
- `DATAHUB_GMS_HOST` / `DATAHUB_GMS_PORT`: Kết nối GMS
- `KAFKA_BOOTSTRAP_SERVER`: Event consumption
- `SCHEMA_REGISTRY_URL`: Schema validation

---

### 5. **datahub-upgrade**

**Mục Đích:** Công việc thiết lập một lần (runs to completion)
- Khởi tạo Elasticsearch indices
- Tạo Kafka topics
- Thiết lập database schema
- Thực hiện version migrations

**Trạng Thái:** Phải hoàn tất thành công trước khi GMS khởi động
- Label: `datahub_setup_job: true`
- Condition: `service_completed_successfully`

---

### 6. **PostgreSQL Setup** (postgres-setup)

**Mục Đích:** Khởi tạo DataHub database
- Tạo database `datahub`
- Thiết lập schema cho metadata storage
- Khởi tạo tables và indexes

**Cấu Hình:**
- Database name: `${DATAHUB_DB_NAME:-datahub}`
- Host: `postgres`
- Credentials: Sử dụng `POSTGRES_USER` / `POSTGRES_PASSWORD`

---

### 7. **Elasticsearch Setup** (elasticsearch-setup)

**Mục Đích:** Khởi tạo Elasticsearch cluster
- Tạo indices cho metadata entities
- Cấu hình mappings và analyzers
- Xử lý index reindexing

**Cấu Hình:**
- Host: `elasticsearch`
- Port: `9200`
- Use SSL: `${ELASTICSEARCH_USE_SSL:-false}`

---

### 8. **Kafka Setup** (kafka-setup)

**Mục Đích:** Pre-creates Kafka topics cho DataHub
- MetadataAuditEvent
- MetadataChangeLog_Versioned
- DataHubUsageEvent
- Và những topics khác...

**Cấu Hình:**
- Bootstrap server: `kafka:29092` (internal)
- Pre-create topics: `${DATAHUB_PRECREATE_TOPICS:-false}`

---

### 9. **Neo4j** (Graph Database)

**Ports:**
- HTTP: `7474` (ánh xạ via `DATAHUB_MAPPED_NEO4J_HTTP_PORT`)
- Bolt: `7687` (ánh xạ via `DATAHUB_MAPPED_NEO4J_BOLT_PORT`)

**Mục Đích:** Lưu trữ entity relationships và lineage
- Mô hình hóa dataset dependencies
- Hỗ trợ impact analysis
- Theo dõi ownership chains

**Thông Tin Đăng Nhập:**
```
Username: neo4j
Password: datahub
```

---

## Cấu Hình

### Biến Môi Trường

#### Cấu Hình DataHub Service

| Biến | Mặc Định | Mục Đích |
|------|----------|---------|
| `DATAHUB_SERVER_TYPE` | `quickstart` | Chế độ server (quickstart, prod) |
| `DATAHUB_TELEMETRY_ENABLED` | `true` | Cho phép telemetry ẩn danh |
| `DATAHUB_DB_NAME` | `datahub` | Tên database PostgreSQL |
| `DATAHUB_MAPPED_GMS_PORT` | `8080` | GMS API port mapping |
| `DATAHUB_MAPPED_FRONTEND_PORT` | `9002` | Frontend UI port mapping |
| `DATAHUB_MAPPED_ELASTIC_PORT` | `9200` | Elasticsearch port mapping |
| `DATAHUB_MAPPED_NEO4J_HTTP_PORT` | `7474` | Neo4j HTTP port |
| `DATAHUB_MAPPED_NEO4J_BOLT_PORT` | `7687` | Neo4j Bolt protocol port |

#### Kết Nối Cơ Sở Dữ Liệu

| Biến | Giá Trị | Mục Đích |
|------|--------|---------|
| `EBEAN_DATASOURCE_DRIVER` | `org.postgresql.Driver` | PostgreSQL JDBC driver |
| `EBEAN_DATASOURCE_HOST` | `postgres:5432` | PostgreSQL host:port |
| `EBEAN_DATASOURCE_URL` | `jdbc:postgresql://...` | Full JDBC connection string |
| `EBEAN_DATASOURCE_USERNAME` | `${POSTGRES_USER}` | Database user |
| `EBEAN_DATASOURCE_PASSWORD` | `${POSTGRES_PASSWORD}` | Database password |

#### Elasticsearch

| Biến | Giá Trị | Mục Đích |
|------|--------|---------|
| `ELASTICSEARCH_HOST` | `elasticsearch` | ES cluster hostname |
| `ELASTICSEARCH_PORT` | `9200` | ES REST API port |
| `ELASTICSEARCH_PROTOCOL` | `http` | ES connection protocol |
| `ELASTICSEARCH_USE_SSL` | `false` | Enable TLS |
| `ELASTICSEARCH_INDEX_BUILDER_MAPPINGS_REINDEX` | `true` | Reindex on startup |
| `ELASTICSEARCH_INDEX_BUILDER_SETTINGS_REINDEX` | `true` | Reindex settings |

#### Kafka

| Biến | Giá Trị | Mục Đích |
|------|--------|---------|
| `KAFKA_BOOTSTRAP_SERVER` | `kafka:29092` | Kafka internal port |
| `KAFKA_SCHEMAREGISTRY_URL` | `http://schema-registry:8081` | Schema Registry |
| `KAFKA_CONSUMER_STOP_ON_DESERIALIZATION_ERROR` | `true` | Fail on bad messages |

#### Neo4j

| Biến | Giá Trị | Mục Đích |
|------|--------|---------|
| `NEO4J_HOST` | `http://neo4j:7474` | HTTP endpoint |
| `NEO4J_URI` | `bolt://neo4j` | Bolt protocol |
| `NEO4J_USERNAME` | `neo4j` | Graph DB username |
| `NEO4J_PASSWORD` | `datahub` | Graph DB password |

#### Cờ Tính Năng (Feature Flags)

| Biến | Giá Trị | Mục Đích |
|------|--------|---------|
| `MAE_CONSUMER_ENABLED` | `true` | Metadata Audit Event consumer |
| `MCE_CONSUMER_ENABLED` | `true` | Metadata Change Event consumer |
| `PE_CONSUMER_ENABLED` | `true` | Platform Event consumer |
| `UI_INGESTION_ENABLED` | `true` | Allow UI-based ingestion setup |
| `METADATA_SERVICE_AUTH_ENABLED` | `false` | Enable authentication |
| `ENTITY_SERVICE_ENABLE_RETENTION` | `true` | Data retention policies |
| `THEME_V2_DEFAULT` | `true` | Use new UI theme |

#### Graph Service

| Biến | Giá Trị | Mục Đích |
|------|--------|---------|
| `GRAPH_SERVICE_IMPL` | `elasticsearch` | Graph backend (elasticsearch or neo4j) |
| `GRAPH_SERVICE_DIFF_MODE_ENABLED` | `true` | Track entity changes |

#### Cài Đặt Memory

| Service | JVM Opts | Heap Size | Giải Thích |
|---------|----------|-----------|-----------|
| `datahub-gms` | `-Xms512m -Xmx768m` | 768MB max | API server + metadata cache |
| `datahub-frontend-react` | `-Xms512m -Xmx512m` | 512MB max | UI rendering |
| `datahub-actions` | `-Xms256m -Xmx768m` | 768MB max | Event processing |
| `datahub-upgrade` | Default | 512MB | One-time job |

### Thêm Biến .env cho DataHub

Thêm vào file `.env`:

```bash
# ============================================
# DATAHUB CONFIGURATION
# ============================================

# Database
DATAHUB_DB_NAME=datahub

# Port Mappings
DATAHUB_MAPPED_GMS_PORT=8080
DATAHUB_MAPPED_FRONTEND_PORT=9002
DATAHUB_MAPPED_ELASTIC_PORT=9200
DATAHUB_MAPPED_NEO4J_HTTP_PORT=7474
DATAHUB_MAPPED_NEO4J_BOLT_PORT=7687

# Server Configuration
DATAHUB_SERVER_TYPE=quickstart
DATAHUB_TELEMETRY_ENABLED=true
METADATA_SERVICE_AUTH_ENABLED=false
GRAPH_SERVICE_IMPL=elasticsearch

# Pre-create Topics
DATAHUB_PRECREATE_TOPICS=false

# Kafka Configuration
KAFKA_CONSUMER_STOP_ON_DESERIALIZATION_ERROR=true
```

---

## Bắt Đầu

### 1. Khởi Động DataHub Profile

```bash
# Đảm bảo core services (Postgres, Kafka, Elasticsearch) đang chạy
docker compose --profile core up -d

# Khởi động DataHub
docker compose --profile datahub up -d
```

### 2. Chờ Services Healthy

```bash
# Kiểm tra tất cả services
docker compose --profile datahub ps

# Theo dõi logs
docker compose logs datahub-gms -f
```

### 3. Truy Cập DataHub UI

1. **Frontend:** http://localhost:9002
2. **GMS API:** http://localhost:8080
3. **Neo4j Browser:** http://localhost:7474
4. **Elasticsearch:** http://localhost:9200

### 4. Kiểm Tra Setup

```bash
# Kiểm tra GMS health
curl http://localhost:8080/health

# Liệt kê Elasticsearch indices
curl http://localhost:9200/_cat/indices

# Kiểm tra Neo4j connectivity
curl http://localhost:7474/
```

---

## Cách Sử Dụng

### Nhập Metadata từ PostgreSQL

Tạo `./infra/datahub/ingestion/recipes/postgres-recipe.yml`:

```yaml
source:
  type: postgres
  config:
    host_port: postgres:5432
    database: demo
    username: admin
    password: admin
    include_views: true

sink:
  type: datahub-rest
  config:
    server: http://datahub-gms:8080

transformers:
  - type: add_dataset_ownership
    config:
      owner_type: "DATAOWNER"
      owner_urn: "urn:li:corpuser:data-team"
```

Chạy ingestion:
```bash
docker compose exec datahub-ingestion datahub ingest -c /recipes/postgres-recipe.yml
```

### Nhập Metadata từ Kafka

Tạo `./infra/datahub/ingestion/recipes/kafka-recipe.yml`:

```yaml
source:
  type: kafka
  config:
    bootstrap: kafka:29092
    schema_registry_url: http://schema-registry:8081

sink:
  type: datahub-rest
  config:
    server: http://datahub-gms:8080
```

---

## Khắc Phục Sự Cố

### GMS Không Khởi Động

**Lỗi:** `Error connecting to Elasticsearch` hoặc database connection failures

**Giải Pháp:**
1. Kiểm tra dependencies hoàn tất:
   ```bash
   docker compose logs datahub-upgrade --tail 50
   ```

2. Kiểm tra PostgreSQL healthy:
   ```bash
   docker compose exec postgres psql -U admin -l | grep datahub
   ```

3. Kiểm tra Elasticsearch:
   ```bash
   curl http://localhost:9200/_cluster/health
   ```

### Memory Usage Cao

**Triệu chứng:** `datahub-gms` container bị kill (OOM)

**Giải Pháp:** Tăng JVM heap trong docker-compose.yml:
```yaml
environment:
  - JAVA_OPTS=-Xms1024m -Xmx1536m  # Tăng từ 768m
```

### Ingestion Failures

**Lỗi:** `Failed to authenticate with GMS` hoặc `Connection timeout`

**Khắc Phục:**
```bash
# Kiểm tra GMS accessibility từ ingestion container
docker compose exec datahub-ingestion curl http://datahub-gms:8080/health

# Kiểm tra recipe syntax
docker compose exec datahub-ingestion datahub ingest -c /recipes/your-recipe.yml --validate
```

### Elasticsearch Index Errors

**Lỗi:** `Failed to create/update mapping`

**Giải Pháp:**
```bash
# Reindex từ GMS
docker compose restart datahub-upgrade
docker compose restart datahub-gms
```

---

## Tài Nguyên

- **Official Docs:** https://datahubproject.io/docs/
- **Ingestion Guide:** https://datahubproject.io/docs/generated/ingestion/sources/
- **API Reference:** https://datahubproject.io/docs/api/graphql/
- **Architecture:** https://datahubproject.io/docs/architecture/architecture
- **Slack Community:** https://slack.datahubproject.io/

---

## Ghi Chú

- DataHub yêu cầu tất cả setup jobs hoàn tất trước khi GMS khởi động (health check được áp dụng)
- Ingestion là asynchronous; metadata xuất hiện sau một khoảng thời gian ngắn
- `datahub` profile bao gồm các phụ thuộc: `postgres`, `kafka`, `elasticsearch`, `schema-registry`
- Giữ plugin path đồng bộ: `${HOME}/.datahub/plugins`
- Để phát triển, sử dụng `DATAHUB_SERVER_TYPE=quickstart`; cho production sử dụng các cài đặt phù hợp

---

**Xem thêm:** [docs/services.md](../../docs/services.md)

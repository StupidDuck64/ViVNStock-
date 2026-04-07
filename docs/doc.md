# Tài liệu kỹ thuật chi tiết nền tảng Lakehouse OSS

## 1. Mục tiêu tài liệu
Tài liệu này được viết lại từ đầu để phục vụ đúng nhu cầu triển khai và vận hành theo góc nhìn Data Architect/Data Engineer:
- Giải thích rõ thư mục nào dùng để làm gì.
- Chỉ ra file cấu hình nào là trọng yếu.
- Mô tả kết nối giữa các dịch vụ theo luồng dữ liệu thực tế.
- Nêu các điểm dễ lỗi khi bật profile và cách kiểm soát rủi ro.

Tài liệu tập trung vào source trong repo hiện tại, đặc biệt là:
- `docker-compose.yml`
- `.env.example`
- `infra/*`
- `docs/*`

## 2. Bức tranh tổng thể hệ thống

### 2.1 Các lớp kiến trúc
Nền tảng được tổ chức theo các lớp chính:
1. Ingestion
- CDC từ PostgreSQL qua Debezium.
- Sự kiện business phát sinh qua data-generator đẩy vào Kafka.
- Luồng dữ liệu bán cấu trúc có thể đi qua NiFi/Flink.

2. Storage và Metadata
- Object storage: MinIO (S3-compatible) cho data lake.
- Relational store: PostgreSQL cho metadata và service DB.
- Analytics serving store: ClickHouse cluster (Keeper + replica).
- Metastore: Hive Metastore cho bảng lakehouse.

3. Processing
- Spark (master, worker, thriftserver) xử lý batch/structured streaming.
- Airflow orchestration DAG + Spark job submission.
- Flink cho streaming stateful (tùy profile).

4. Serving và BI
- Trino query federation/lake query.
- Superset dashboard/semantic layer.
- Lakehouse portal (Nginx) làm mặt tiền truy cập.

5. Security, IAM, Secrets
- Keycloak làm OIDC IdP.
- Vault cấp phát secrets runtime qua entrypoint scripts.
- Ranger đồng bộ user/quyền (nếu bật profile ranger).
- OAuth2 Proxy bảo vệ portal.

6. Observability
- Prometheus, Grafana, Alertmanager.
- Loki, ELK stack (Elasticsearch/Kibana/Logstash) theo profile monitoring.

### 2.2 Triết lý vận hành theo profile
Compose được chia profile để tránh bật full stack cùng lúc.
- `core`: data services chính.
- `airflow`: orchestration runtime.
- `datahub`: data catalog DataHub stack.
- `openmetadata`: metadata stack khác (OpenMetadata).
- `monitoring`: observability.
- `portal`: dashboard + oauth2-proxy.
- `flink`, `ranger`, `superset`, `trino`, `clickhouse`... bật mở rộng theo nhu cầu.

Khuyến nghị quan trọng:
- Không bật `datahub` và `openmetadata` cùng lúc trên máy RAM thấp nếu chưa tinh chỉnh.
- Cần coi `core` là nền, sau đó ghép thêm từng profile theo use case.

## 3. Luồng dữ liệu end-to-end

### 3.1 CDC từ PostgreSQL
1. PostgreSQL sinh WAL/changes.
2. Debezium Kafka Connect đọc CDC từ PostgreSQL.
3. Debezium publish event vào Kafka topic.
4. Schema Registry quản lý schema (Avro/compatibility).
5. Consumer downstream (Spark/Flink/service khác) đọc topic để xử lý.

Điểm kiểm soát:
- User CDC (`POSTGRES_CDC_USER`) phải có quyền replication phù hợp.
- Topic nội bộ của Connect (`my_connect_configs`, `my_connect_offsets`, `my_connect_statuses`) cần ổn định.
- Bootstrap server nội bộ cần dùng `kafka:29092` trong container network.

### 3.2 Event generation mô phỏng nghiệp vụ
1. `data-generator` tạo event orders/payments/shipments/inventory/interactions.
2. Encode schema qua Schema Registry.
3. Publish vào Kafka topic business.
4. Đồng thời seed/mirror một phần vào PostgreSQL demo.

Điểm kiểm soát:
- Healthcheck của data-generator đã kiểm tra đồng thời PostgreSQL và Schema Registry.
- Cần nhất quán tên topic trong env (`TOPIC_ORDERS`, `TOPIC_PAYMENTS`, ...).

### 3.3 Bronze/Silver processing bằng Airflow + Spark
1. Airflow DAG gọi Spark jobs trong `infra/airflow/processing/spark/jobs`.
2. Job đọc nguồn từ Kafka/PostgreSQL/S3.
3. Ghi dữ liệu Bronze/Silver (thường lên MinIO + catalog metadata Hive).
4. Trino/Spark Thrift/Superset truy vấn layer phục vụ phân tích.

Điểm kiểm soát:
- Airflow connection `spark_default` và `minio` được tạo trong `airflow-init`.
- Secrets của MinIO, DB có thể bị override bởi Vault entrypoint.

### 3.4 Serving và BI
- Trino đọc từ Hive Metastore + MinIO.
- Superset kết nối Trino/ClickHouse/PostgreSQL để dựng dashboard.
- Grafana đọc Prometheus/ClickHouse/Loki theo datasource provisioning.

### 3.5 Security flow (OIDC)
1. User truy cập portal hoặc UI service.
2. OAuth2 Proxy chuyển hướng sang Keycloak.
3. Keycloak trả token OIDC.
4. Service phía sau xác thực token (Airflow/Superset/DataHub/OpenMetadata tùy config).

## 4. Service connectivity map

## 4.1 Nhóm nền tảng cốt lõi
- `postgres`
  - Được dùng bởi: Airflow, Hive Metastore, Keycloak DB, DataHub, OpenMetadata, service khác.
- `minio`
  - Được dùng bởi: Spark, Flink, ingestion jobs, data lake storage.
- `kafka`
  - Producer: Debezium, data-generator.
  - Consumer: processing jobs, DataHub/OpenMetadata connector stack.
- `schema-registry`
  - Dùng bởi producer/consumer dùng Avro schema.
- `redis`
  - Dùng bởi Airflow Celery backend/broker cache và một số app cache.

## 4.2 Nhóm compute và orchestration
- `airflow-apiserver`, `airflow-scheduler`, `airflow-worker`, `airflow-triggerer`, `airflow-dag-processor`
  - Phụ thuộc: Redis, PostgreSQL, airflow-init.
  - Tương tác: Spark, MinIO, Oracle connection (nếu cấu hình).
- `spark-master`, `spark-worker-*`, `spark-thriftserver`
  - Phụ thuộc: MinIO, Hive Metastore, Kafka.

## 4.3 Nhóm security
- `vault`
  - Chứa secret nguồn.
- `vault-init`
  - Seed secret vào Vault KV.
- `keycloak-db`, `keycloak`, `keycloak-init`
  - Cung cấp IAM/OIDC cho platform.
- `oauth2-proxy`
  - Cổng xác thực trước portal.

## 4.4 Nhóm governance/catalog
- `datahub-*` stack
  - Dùng Kafka, Elasticsearch, PostgreSQL, Schema Registry.
- `openmetadata-*` stack
  - Dùng PostgreSQL, Elasticsearch, Airflow ingestion.
- `ranger-admin`, `ranger-usersync`
  - Kết nối Keycloak và policy services.

## 4.5 Nhóm observability
- `prometheus` scrape metrics.
- `grafana` hiển thị dashboard.
- `alertmanager` gửi cảnh báo.
- `loki` cho log aggregation.
- `elasticsearch/kibana/logstash` cho ELK (nếu bật).

## 5. Cấu hình trọng yếu theo file

### 5.1 `docker-compose.yml`
Đây là file kiến trúc triển khai quan trọng nhất.

Các điểm bắt buộc hiểu:
1. Anchor `x-airflow-common`
- Gom cấu hình dùng chung cho toàn bộ Airflow services.
- Nếu sửa env Airflow, sửa tại đây để tránh lệch giữa scheduler/worker/apiserver.

2. `depends_on` + `condition`
- Đã dùng `service_healthy`/`service_completed_successfully` ở nhiều service.
- Dù vậy, cần nhớ đây không thay thế hoàn toàn retry logic ứng dụng.

3. `profiles`
- Quyết định service nào chạy trong từng chế độ.
- Tránh bật profile không cần thiết để giảm tài nguyên.

4. `deploy.resources`
- Có đặt limit/reservation cho nhiều service.
- Trên Docker Compose local, đây chủ yếu là gợi ý; vẫn nên giám sát thực tế.

5. Mapping ports
- Có nhiều cổng remap để tránh trùng: ví dụ Keycloak 18084, Trino 8080, Airflow 8085.
- Cần chuẩn hóa host IP trong env để tránh hardcode sai khi đổi máy.

6. Vault integration pattern
- Nhiều service dùng `vault-entrypoint.sh` để override secret từ Vault.
- Nếu script vault lỗi, service vẫn có thể chạy bằng fallback từ `.env` nhưng rủi ro bảo mật cao.

### 5.2 `.env.example`
Đây là baseline biến môi trường. Nhóm biến chính:
- DB credentials: `POSTGRES_*`
- Object storage: `MINIO_*`
- Analytics DB: `CLICKHOUSE_*`
- Airflow auth/executor/DB/celery
- Kafka KRaft config
- Debezium topic config
- Schema Registry endpoints
- Superset admin

Nguyên tắc:
- `.env.example` chỉ là template.
- Không dùng secret production thật trong repo.
- Với môi trường thật, ưu tiên Vault/AppRole thay vì token dev.

### 5.3 Airflow OAuth config
File: `infra/airflow/config/webserver_config.py`
- Cấu hình `AUTH_TYPE = AUTH_OAUTH` với provider Keycloak.
- Security manager tùy biến map role Keycloak sang role Airflow.
- Role mapping hiện có: `airflow-admin/platform-admin -> Admin`, `airflow-user/data-engineer -> Op`, `airflow-viewer/data-analyst -> Viewer`.

Điểm cần chú ý:
- `client_secret` đang ở dạng placeholder `CHANGE_ME_AIRFLOW_SECRET`.
- URL redirect đang hardcode `127.0.0.1`; nếu deploy remote cần đổi chuẩn.

### 5.4 Spark/Hive/Trino config
Các file quan trọng:
- `infra/spark/spark-defaults.conf`
- `infra/spark/core-site.xml`
- `infra/spark/hive-site.xml`
- `infra/hive-metastore/config/hive-site.xml`
- `infra/trino/config/config.properties`

Mục tiêu cấu hình:
- S3A connector trỏ MinIO.
- Catalog metadata qua Hive Metastore.
- Trino đọc lakehouse tables.

### 5.5 ClickHouse cluster config
Các file quan trọng:
- `infra/clickhouse/config.xml`
- `infra/clickhouse/users.xml`
- `infra/clickhouse/keeper/keeper_config.xml`

Vai trò:
- Keeper cung cấp coordination/quorum.
- 2 node ClickHouse replicate trong cùng shard.
- user/password/db lấy từ env và có thể override bởi Vault.

### 5.6 Keycloak và bootstrap scripts
Các file quan trọng:
- `infra/keycloak/init.sh`
- `infra/keycloak/vault-entrypoint.sh`
- `add_aud_mapper.py`
- `append_portal_client.py`

Ý nghĩa:
- Hai script Python ở root là script hỗ trợ chỉnh realm JSON (one-off), không phải runtime core.
- Dùng khi cần bổ sung mapper/client cho realm import.

### 5.7 Vault setup
Các file quan trọng:
- `infra/vault/init-secrets.sh`
- `infra/vault/setup-approles.sh`
- `infra/vault/policies/*`

Mục tiêu:
- Seed secret KV cho platform.
- Tạo policy/AppRole cho từng service để bỏ token root dev.

## 6. Mục đích từng thư mục cấp cao

### 6.1 `.devcontainer/`
- Cấu hình môi trường dev container cho VS Code.
- Dùng để chuẩn hóa toolchain giữa các thành viên.

### 6.2 `.gitlab/`
- CI/CD pipeline templates và automation job cho GitLab.
- Liên quan build image, scan, test, deploy workflow.

### 6.3 `docs/`
- Tài liệu kiến trúc, service docs index, troubleshooting, lộ trình học.
- Là nơi nên cập nhật trước khi merge thay đổi hạ tầng.

### 6.4 `infra/`
- Trọng tâm vận hành: Dockerfile, entrypoint, config cho từng service.
- Đây là “source of truth” cho runtime behavior.

### 6.5 `notebooks/`
- Ví dụ học tập và thực hành phân tích dữ liệu.
- Không phải nguồn cấu hình production.

### 6.6 `lakehouse-oss/`
- Thư mục placeholder/legacy (hiện không chứa runtime logic chính).

## 7. Mục đích từng thư mục trong `infra/`

### 7.1 `infra/airflow/`
- Chứa Dockerfile Airflow custom.
- Chứa DAG orchestration và Spark jobs được gọi bởi DAG.
- Chứa `vault-entrypoint.sh` để lấy secret runtime.

File nổi bật:
- `infra/airflow/dags/bronze_events_kafka_stream_dag.py`
- `infra/airflow/dags/silver_retail_star_schema_dag.py`
- `infra/airflow/processing/spark/jobs/silver_retail_service.py`

### 7.2 `infra/minio/`
- Build image MinIO kèm script setup buckets/policies.
- `entrypoint.sh` và `setup-minio.sh` quyết định bootstrap data lake namespace.

### 7.3 `infra/postgres/`
- Build PostgreSQL custom.
- `init-databases.sh` tạo nhiều database theo `POSTGRES_MULTIPLE_DATABASES`.
- Nơi gốc dữ liệu metadata và service DB.

### 7.4 `infra/kafka/`
- Build Kafka image theo KRaft mode.
- Không phụ thuộc Zookeeper.
- Cấu hình listeners internal/external quan trọng cho connectivity.

### 7.5 `infra/schema-registry/`
- Đăng ký schema và bootstrap schema script (`init-schemas.sh`).
- Liên kết chặt với Kafka internal bootstrap.

### 7.6 `infra/debezium/`
- Kafka Connect cho CDC.
- `start-with-connectors.sh` hỗ trợ tạo connector khi khởi động.

### 7.7 `infra/clickhouse/`
- Cấu hình cluster analytics DB.
- `keeper/` riêng cho coordination quorum.

### 7.8 `infra/spark/`
- Dockerfile Spark chung + Dockerfile thriftserver.
- Chứa config Hadoop/S3A/Hive tích hợp lakehouse.

### 7.9 `infra/hive-metastore/`
- Service metastore dùng PostgreSQL backend.
- Chứa config liên quan Ranger plugin khi bật governance.

### 7.10 `infra/trino/`
- Query engine phục vụ BI và ad-hoc SQL.
- `docker-entrypoint.sh` và `config/*` quyết định startup/catalog behavior.

### 7.11 `infra/superset/`
- BI server + worker.
- `superset_config_keycloak.py` cho OIDC integration.
- `provisioning/databases.yaml` để bootstrap datasource.

### 7.12 `infra/keycloak/`
- IAM server + keycloak-db image.
- `init.sh` để tạo realm/client/role mappings ban đầu.

### 7.13 `infra/vault/`
- Secrets management bootstrap.
- Chuẩn hóa policy-based secret access.

### 7.14 `infra/flink/`
- Streaming compute runtime.
- Có thêm nginx proxy và OIDC hardening layer.
- Vault entrypoint patch secret vào `FLINK_PROPERTIES` trước khi chạy.

### 7.15 `infra/datahub/`
- Full stack metadata platform DataHub (gms, frontend, actions, setup jobs).
- `ingestion/recipes/*` định nghĩa nguồn metadata ingest.

### 7.16 `infra/openmetadata/`
- Full stack OpenMetadata và ingestion.
- Có script migrate và ingestion orchestration riêng.

### 7.17 `infra/ranger-admin/`
- Ranger admin + user sync với Keycloak.
- File `trino_service_setup.py` hỗ trợ khởi tạo policy/service integration.

### 7.18 `infra/portal/`
- Frontend landing portal qua Nginx.
- Phối hợp với oauth2-proxy để SSO truy cập tập trung.

### 7.19 `infra/prometheus/`, `infra/grafana/`, `infra/alertmanager/`, `infra/loki/`
- Observability stack: metrics + dashboards + alerts + logs.

### 7.20 `infra/elasticsearch/`, `infra/kibana/`, `infra/logstash/`
- ELK stack cho log/search/analysis (profile monitoring).

### 7.21 `infra/nifi/`
- Dataflow engine cho ingest/ETL visual flow.
- Có cơ chế lấy secret admin từ Vault.

### 7.22 `infra/data-generator/`
- Mô-đun sinh dữ liệu mô phỏng theo domain retail/logistics.
- Cấu trúc code theo adapters/services/ports khá rõ ràng.

## 8. Bản đồ cổng dịch vụ quan trọng

Nhóm truy cập phổ biến:
- MinIO API: `9000`
- MinIO Console: `9001`
- Kafka external: `9092`
- Schema Registry: `8081`
- Kafka UI: `8082`
- Debezium: `8083`
- Airflow API/UI: `8085`
- Trino: `8080`
- Spark Master UI: `8088`
- Superset: `8089`
- PostgreSQL host mapped: `15432`
- Keycloak: `18084`
- Vault: `8200`
- Prometheus: `9094`
- Grafana: `3000`
- OpenMetadata: `8585`
- DataHub frontend: `9004` (mapped)
- Portal: `3100`
- OAuth2 Proxy: `4180`

Lưu ý:
- Trong container network, nhiều service dùng cổng nội bộ khác với host mapped.
- Ví dụ Kafka internal dùng `kafka:29092` cho hầu hết service nội bộ.

## 9. Trình tự khởi động khuyến nghị

### 9.1 Chế độ tối thiểu để chạy lakehouse lõi
1. Chuẩn bị env:
- copy `.env.example` thành `.env` và chỉnh credentials.

2. Khởi động nền:
- `docker compose --profile core up -d postgres minio kafka schema-registry redis hive-metastore`

3. Bổ sung compute:
- `docker compose --profile core up -d spark-master spark-worker-1 trino`

4. Bổ sung orchestration:
- `docker compose --profile airflow up -d`

5. Bổ sung BI:
- `docker compose --profile superset up -d`

### 9.2 Chế độ metadata governance
- Với DataHub:
  - `docker compose --profile datahub up -d`
- Với OpenMetadata:
  - `docker compose --profile openmetadata up -d`

Khuyến nghị:
- Chỉ chọn một metadata stack chính ở môi trường dev tài nguyên thấp.

### 9.3 Chế độ security nâng cao
- Bật Vault + Keycloak + Portal:
  - `docker compose --profile core --profile portal up -d vault vault-init keycloak-db keycloak keycloak-init oauth2-proxy lakehouse-portal`

## 10. Điểm nghẽn kỹ thuật và rủi ro chính

### 10.1 Hardcode host/IP
- Một số chỗ dùng IP cụ thể (`192.168.26.181`) trong Kafka advertised listeners và Keycloak hostname.
- Khi đổi máy/mạng, các callback hoặc bootstrap có thể fail.

Khuyến nghị:
- Chuẩn hóa qua biến env, tránh hardcode trực tiếp.

### 10.2 Secret management ở trạng thái chuyển tiếp
- Nhiều service có fallback từ `.env` và override bởi Vault token dev.
- Nếu giữ `VAULT_TOKEN=dev-root-token` lâu dài là rủi ro bảo mật.

Khuyến nghị:
- Chuyển dần sang AppRole per service và rotate secret định kỳ.

### 10.3 Trùng profile gây quá tải tài nguyên
- Bật `core + datahub + openmetadata + monitoring + airflow` cùng lúc dễ quá RAM.

Khuyến nghị:
- Bật profile theo phase.
- Giảm heap JVM các service nặng (GMS, ES, Kafka) nếu chỉ dev.

### 10.4 Duplicate/khai báo lặp
- Có một số dòng lặp trong compose (ví dụ volume mount hoặc port khai báo 2 lần ở vài service).

Khuyến nghị:
- Dọn compose định kỳ để giảm drift và khó debug.

## 11. Checklist kiểm tra sau khi bật stack

### 11.1 Hạ tầng cốt lõi
- PostgreSQL healthy.
- Kafka healthy và có thể list topic.
- Schema Registry trả về endpoint root.
- MinIO API và console truy cập được.

### 11.2 Pipeline
- Debezium connector ở trạng thái RUNNING.
- Airflow scheduler + worker healthy.
- DAG Spark submit thành công.

### 11.3 Truy vấn
- Trino query được bảng metadata từ Hive.
- Superset kết nối datasource không lỗi.

### 11.4 Bảo mật
- Keycloak realm/client đã được init.
- OAuth2 proxy redirect/login callback thành công.
- Service lấy secret đúng từ Vault.

### 11.5 Quan sát hệ thống
- Prometheus scrape target up.
- Grafana datasource ready.
- Alertmanager nhận route rule.

## 12. Danh sách file trọng yếu cần nắm trước khi sửa hệ thống

### 12.1 Runtime orchestration
- `docker-compose.yml`
- `.env.example`
- `start-lakehouse.sh`

### 12.2 Airflow + Spark
- `infra/airflow/Dockerfile`
- `infra/airflow/vault-entrypoint.sh`
- `infra/airflow/config/webserver_config.py`
- `infra/airflow/dags/*.py`
- `infra/airflow/processing/spark/jobs/*.py`
- `infra/spark/spark-defaults.conf`

### 12.3 Streaming
- `infra/kafka/Dockerfile`
- `infra/schema-registry/init-schemas.sh`
- `infra/debezium/start-with-connectors.sh`

### 12.4 Storage/Query
- `infra/postgres/init-databases.sh`
- `infra/minio/setup-minio.sh`
- `infra/hive-metastore/config/hive-site.xml`
- `infra/trino/config/config.properties`
- `infra/clickhouse/config.xml`
- `infra/clickhouse/keeper/keeper_config.xml`

### 12.5 Security
- `infra/vault/init-secrets.sh`
- `infra/vault/setup-approles.sh`
- `infra/keycloak/init.sh`
- `infra/superset/superset_config_keycloak.py`
- `add_aud_mapper.py`
- `append_portal_client.py`

### 12.6 Metadata/Governance
- `infra/datahub/*`
- `infra/openmetadata/*`
- `infra/ranger-admin/*`

### 12.7 Monitoring
- `infra/prometheus/config/prometheus.yml`
- `infra/prometheus/config/alert-rules.yml`
- `infra/grafana/config/provisioning/datasources/datasources.yml`
- `infra/loki/config/loki-config.yml`

## 13. Gợi ý chuẩn hóa kiến trúc khi triển khai thực tế

### 13.1 Chuẩn hóa theo môi trường
- Tách `env/dev`, `env/staging`, `env/prod`.
- Chia compose override cho từng môi trường.

### 13.2 Chuẩn hóa identity
- Dùng tên miền cố định cho callback OIDC.
- Chuẩn hóa realm/client naming convention.

### 13.3 Chuẩn hóa data contract
- Áp dụng naming topic có version (`domain.entity.v1`).
- Bật compatibility policy cho Schema Registry.

### 13.4 Chuẩn hóa observability
- Mỗi service có label, metrics endpoint, alert rule tối thiểu.
- Thêm dashboard health theo lớp: ingest, process, serve, security.

### 13.5 Chuẩn hóa deployment
- Tài liệu runbook theo từng profile.
- Có script smoke test sau deploy.
- Có quy trình rollback cho thay đổi compose và config.

## 14. Kết luận
`lakehouse-oss` trong repo này là một nền tảng dữ liệu đa dịch vụ có độ bao phủ rộng (ingest, process, serve, security, governance, observability), phù hợp làm sandbox kiến trúc data platform hoàn chỉnh.

Để vận hành ổn định, thứ tự ưu tiên kỹ thuật nên là:
1. Ổn định `core` profile trước.
2. Chuẩn hóa secret management (giảm phụ thuộc root token dev).
3. Chuẩn hóa OIDC host/callback để tránh lỗi đăng nhập phân tán.
4. Mở rộng dần metadata/monitoring theo năng lực tài nguyên máy chủ.

Nếu cần đào sâu bước tiếp theo, nên viết thêm 3 tài liệu chuyên biệt:
- Runbook sự cố (incident handbook) theo service.
- Matrix cấu hình theo môi trường (dev/stage/prod).
- Data contract catalog cho topic/schema/table chuẩn hóa toàn nền tảng.

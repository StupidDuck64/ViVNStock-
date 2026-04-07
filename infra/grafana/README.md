# Monitoring Infrastructure Documentation

## Tổng quan dự án

Dự án triển khai hệ thống giám sát toàn diện cho infrastructure sử dụng ELK Stack, Prometheus, Grafana và Loki. Hệ thống được thiết kế để giám sát sâu các thành phần quan trọng của data platform.

### Stack công nghệ

- **Metrics Collection:** Prometheus
- **Log Aggregation:** Loki, ELK Stack
- **Visualization:** Grafana
- **Container Monitoring:** cAdvisor, Node Exporter, Postgres Exporter

### Thứ tự ưu tiên (Priority)

1. **P0 – Critical:** Sập là dừng hệ thống / mất dữ liệu / ảnh hưởng trực tiếp business
2. **P1 – High:** Ảnh hưởng lớn, degrade hiệu năng, pipeline chậm hoặc sai
3. **P2 – Medium:** Ảnh hưởng gián tiếp, chủ yếu support / UX / quản trị
4. **P3 – Low:** Tiện ích, tooling, không ảnh hưởng core flow

### Monitoring Levels

1. **Deep:** Giám sát chi tiết, bao gồm tất cả metrics quan trọng
2. **Standard:** Giám sát các metrics cơ bản và quan trọng
3. **Basic:** Giám sát tổng quan health check

## Timeline thực hiện

### Phase 1: Foundation Setup (29/12/2025 - 10/01/2026) ✅
**Status:** COMPLETED

Triển khai các thành phần cơ bản:
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Prometheus
- Grafana
- Loki
- 2 Dashboard chính cho Docker/Kubernetes monitoring, 1 Dashboard cho MinIO, 1 Dashboard cho ClickHouse

**Priority:** Critical  
**Monitor Level:** Deep

### Phase 2: Core Services (12/01/2026 - 16/01/2026)
**Status:** IN PROGRESS

Triển khai monitoring cho các dịch vụ quan trọng:
- PostgreSQL
- Hive Metastore

**Priority:** Critical  
**Monitor Level:** Deep

---

## Dashboard đã triển khai

### 1. Docker Container Dashboard
**Priority:** Critical | **Status:** ✅ COMPLETED

Dashboard giám sát tổng quan về hiệu suất và tài nguyên của từng container riêng lẻ trong hệ thống Docker/Kubernetes.

#### Mục tiêu giám sát
- Phát hiện sớm vấn đề: Xác định container nào đang tiêu thụ tài nguyên bất thường (CPU spike, memory leak, disk I/O cao)
- Tối ưu hóa tài nguyên: Đánh giá xem container nào cần điều chỉnh resource limits/requests
- Troubleshooting nhanh: Khi có incident, nhanh chóng xác định container gây ra vấn đề

#### Nội dung giám sát
- **File System Usage:** Dung lượng đĩa mỗi container đang sử dụng
- **CPU Usage:** Phần trăm CPU tiêu thụ, phát hiện CPU throttling
- **Memory Usage & Memory Cache:** RAM thực tế và cache memory, theo dõi memory leak
- **Network Receive/Send:** Lưu lượng mạng vào/ra, phát hiện traffic bất thường

---

### 2. Docker Host Dashboard
**Priority:** Critical | **Status:** ✅ COMPLETED

Dashboard giám sát hiệu suất tổng thể của host/node chạy Docker, từ tầng phần cứng đến hệ điều hành.

#### Mục tiêu giám sát
- Giám sát infrastructure: Theo dõi sức khỏe của physical/virtual server
- Capacity planning: Đánh giá khi nào cần scale thêm node hoặc upgrade phần cứng
- Performance tuning: Tối ưu hóa OS, network, disk configuration
- Phát hiện bottleneck: Xác định tài nguyên nào đang là điểm nghẽn

#### Nội dung giám sát

**Overview Metrics:**
- **All Server Overview:** Tổng quan về tất cả nodes trong cluster, so sánh performance
- **Quick CPU / Mem / Disk:** Metrics nhanh về ba tài nguyên quan trọng

**Detailed Metrics:**
- **Basic CPU / Mem / Net / Disk:** Chi tiết breakdown theo CPU types, memory types, network traffic
- **CPU / Memory / Net / Disk:** Metrics chi tiết nhất (min, max, last values)

**Memory Deep Dive:**
- **Memory Meminfo:** Phân tích chi tiết cấu trúc bộ nhớ từ /proc/meminfo
- **Memory Vmstat:** Virtual memory statistics, page in/out, swap, page faults

**Storage Monitoring:**
- **Storage Disk:** IOPS, throughput, wait time, queue depth
- **Storage Filesystem:** Filesystem usage, inodes availability, file descriptors

**Network Monitoring:**
- **Network Traffic:** Throughput và packet statistics per interface
- **Network Sockstat:** TCP/UDP socket statistics, connection states
- **Network Netstat:** Protocol statistics, TCP retransmissions

**System Health:**
- **Systemd:** Units state, sockets status, service monitoring
- **System Processes:** Process activity, states, CPU saturation, PIDs/threads limits
- **System Timesync:** NTP/chrony time synchronization
- **System Misc:** Context switches, interrupts, load average, entropy pool

**Hardware:**
- **Hardware Misc:** Hardware sensors (fan speed, temperature)
- **Node Exporter:** Exporter health metrics

> **Note:** Phụ thuộc vào hệ thống và phần cứng sẽ có thể lược bớt các panel không có data. Các dashboard có thể chia nhỏ thành các dashboard riêng nếu cần.

---

### 3. MinIO Distributed Comprehensive Monitoring
**Priority:** Critical | **Status:** ✅ COMPLETED

Dashboard giám sát hệ thống lưu trữ đối tượng MinIO trong chế độ phân tán, cung cấp cái nhìn toàn diện về hiệu suất lưu trữ và tính sẵn sàng của dữ liệu.

#### Mục tiêu giám sát
- Theo dõi cluster health
- Phát hiện sớm hardware failures
- Đánh giá performance bottlenecks
- Đảm bảo data consistency qua erasure coding
- Monitor API performance
- Capacity planning

#### Nội dung giám sát

**Cluster Level:**
- **Cluster Overview:** Health status, capacity, quorum, data distribution
- **Cluster API Performance:** Request rate, errors, in-flight requests

**Node Level:**
- **Distributed Node Details:** CPU, memory, disk usage, file descriptors, drive health, I/O latency
- **Drive Throughput, IOPS & Syscalls:** Disk performance metrics, I/O patterns

**Bucket Level:**
- **Bucket Specific Details:** Data stored, objects count, receive/sent rate, object size distribution
- **Per-Bucket API Performance:** Request rate, errors, bandwidth per bucket

**Replication:**
- **Node Replication:** Active workers, link latency, queued size, transfer rate
- **Bucket Replication:** Data received/sent, failed operations, replication latency

---

### 4. ClickHouse and Keeper Comprehensive Monitoring
**Priority:** Critical | **Status:** ✅ COMPLETED

Dashboard giám sát Cơ sở dữ liệu ClickHouse và thành phần điều phối Keeper, tập trung vào hiệu suất truy vấn OLAP và tính toàn vẹn của cluster.

#### Mục tiêu giám sát
- Hiệu năng truy vấn (Query Execution Performance)
- Hoạt động ghi dữ liệu (Insert & Merge Activity)
- Sức khỏe của Cluster

#### Nội dung giám sát

**Service Overview:**
- **ClickHouse Service Overview:** Nodes info, memory usage, connections, slow reads, MergeTree metrics

**Query Monitoring:**
- **Queries Statistic Summary:** QPS, failed queries, average query time
- **Query Execution Performance:** Slow queries, memory consumers, failed queries, query logs

**Data Operations:**
- **Insert Activity Summary:** Inserted rows/bytes, delayed inserts, rejected inserts
- **Select Activity Summary:** Selected parts/marks/ranges/bytes/rows per second
- **Merge Activity Summary:** Merge operations, execution time, memory usage
- **Mutate Activity Summary:** UPDATE/DELETE operations monitoring

**Background Operations:**
- **Background Pool Summary:** Common, move, buffer flush, merge pools
- **Backup & Restore Summary:** I/O threads monitoring

**Performance:**
- **Storage IO Performance:** Read/write operations, file errors, bandwidth
- **Cache Performance Summary:** Hit/miss rates, cache optimization

**Replication & Distribution:**
- **Replication Activity Summary:** Failed replicas, fetch parts, data consistency
- **MergeTree Parts Statistics:** Parts count and status
- **Distributed Operations Summary:** Connection monitoring, delayed/rejected requests

**Keeper Monitoring:**
- **ClickHouse Client for Keeper:** Connection latency, exceptions, response traffic
- **Keeper Service Overview:** Outstanding requests, RPS, commit failures

---

## Dashboard đang triển khai

### 5. PostgreSQL Monitoring
**Priority:** Critical | **Monitor Level:** Deep | **Status:** 🔄 PLANNED

Giám sát chi tiết database PostgreSQL.

---

### 6. Hive Metastore Monitoring
**Priority:** Critical | **Monitor Level:** Deep | **Status:** 🔄 PLANNED

Giám sát metadata service cho Hive.

---

### Thứ tự ưu tiên

Các hạng mục giám sát được sắp xếp theo thứ tự ưu tiên:
1. **Critical Priority:** Docker/Kubernetes, MinIO, ClickHouse, PostgreSQL, Hive, Spark, Flink, Kafka, Debezium, Airflow
2. **High Priority:** Schema Registry, Nifi, Trino, Redis, Elasticsearch, Ranger, Keycloak, Vault
3. **Medium Priority:** Superset
4. **Low Priority:** Kafka UI

## Hướng dẫn sử dụng

### Truy cập dashboards

- **Grafana:** http://localhost:3000
- **Prometheus:** http://localhost:9090
- **Kibana:** http://localhost:5601

### Import dashboard

1. Vào Grafana UI
2. Navigate to Dashboards → Import
3. Upload JSON file từ thư mục `dashboards/`
4. Select data source
5. Click Import

---

## Changelog

### 2025-01-10
- ✅ Hoàn thành Docker Container Dashboard
- ✅ Hoàn thành Docker Host Dashboard
- ✅ Hoàn thành MinIO Distributed Monitoring
- ✅ Hoàn thành ClickHouse and Keeper Monitoring

### 2025-01-12
- 🔄 Bắt đầu Phase 2: Core Services Monitoring

---

**Last Updated:** 2026-01-12
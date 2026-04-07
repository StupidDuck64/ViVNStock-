# Danh sách Tasks cho Sinh viên Thực tập (Lakehouse Platform)

Dựa trên kiến trúc hiện tại của dự án `lakehouse-oss` (sử dụng Docker Compose với các thành phần như MinIO, Kafka, Spark, Trino, Airflow, ClickHouse, Superset, v.v.), dưới đây là danh sách các task chi tiết để giao cho sinh viên thực tập. Danh sách được chia làm 2 giai đoạn: **Giai đoạn 1** (Hoàn thiện nền tảng Docker Compose hiện tại) và **Giai đoạn 2** (Chuyển đổi/Phát triển trên nền tảng Kubernetes - K8s).

---

## Giai đoạn 1: Hoàn thiện và tối ưu nền tảng Lakehouse hiện tại (Docker Compose)

### 1. Tích hợp Quản lý Định danh và Truy cập (IAM/SSO)
- [ ] **Task 1.1**: Tích hợp Keycloak với Apache Superset để hỗ trợ đăng nhập Single Sign-On (SSO).
- [ ] **Task 1.2**: Tích hợp Keycloak với Apache Airflow và MinIO Console.
- [ ] **Task 1.3**: Tích hợp Keycloak với JupyterLab.
- [ ] **Task 1.4**: Cấu hình Role-Based Access Control (RBAC) trên Keycloak và map các role này xuống Superset, Airflow.
- [ ] **Task 1.5 (Portal IAM)**: Nâng cấp mã nền tảng **Lakehouse Portal** (file `app.js`): Giải mã (decode) Token từ OAuth2 Proxy để hiển thị thông tin Name, Email và Avatar người dùng lên thanh Dashboard.
- [ ] **Task 1.6 (Access Control UI)**: Viết thêm logic Javascript để ẩn/hiện hoặc vô hiệu hóa (`disabled`) các thẻ Services trên giao diện Portal dựa vào mảng `roles` của Token (Ví dụ: Tài khoản `intern` không thể click truy cập Ranger Admin).

### 2. Tích hợp Quản lý Bảo mật Dữ liệu (Apache Ranger)
- [ ] **Task 2.1**: Triển khai Apache Ranger (hiện đang có trong profile `ranger` nhưng cần hoàn thiện config).
- [ ] **Task 2.2**: Cấu hình Ranger Plugin cho Hive Metastore và Trino để quản lý quyền truy cập Table/Column-level.
- [ ] **Task 2.3**: Viết tài liệu (Walkthrough) hướng dẫn cách phân quyền một bảng dữ liệu qua Ranger UI và xác thực bằng cách truy vấn qua Trino.

### 3. Monitoring & Observability
- [ ] **Task 3.1**: Triển khai Prometheus và Grafana qua Docker Compose.
- [ ] **Task 3.2**: Thu thập metrics từ các service (JMX exporter cho Kafka/Spark, Airflow metrics, MinIO Prometheus endpoint).
- [ ] **Task 3.3**: Xây dựng các Grafana Dashboards cơ bản để giám sát tài nguyên (CPU, RAM của container) và hiệu năng của các dịch vụ lõi (Kafka lag, Spark jobs, Airflow DAGs).
- [ ] **Task 3.4**: Triển khai giải pháp tập trung Log (VD: ELK stack hoặc Fluent-bit + Loki) cho các containers.

### 4. Quản lý Secret tập trung (HashiCorp Vault)
- [ ] **Task 4.1**: Thay thế việc sử dụng file `.env` thuần túy bằng việc inject secret từ Vault vào các services (Airflow, Trino, Superset) lúc khởi động.
- [ ] **Task 4.2**: Xây dựng script tự động khởi tạo (init) các cấu hình và secret cần thiết vào Vault khi lần đầu chạy hệ thống.

### 5. Data Engineering & Thực chiến Pipeline (Use-cases)
- [ ] **Task 5.1 (Batch Pipeline)**: Viết DAG trên Airflow kết hợp Spark Submit để đọc dữ liệu thô (Bronze) từ Data Generator, làm sạch lịch sử và ghi lại dưới định dạng Apache Iceberg/Delta Lake (Silver) trên MinIO.
- [ ] **Task 5.2 (Modeling)**: Dùng dbt (data build tool) hoặc Trino SQL để tổng hợp dữ liệu từ lớp Silver lên lớp Gold (Data Mart) phục vụ BI.
- [ ] **Task 5.3 (Streaming Pipeline)**: Xây dựng luồng Change Data Capture (CDC): PostgreSQL -> Debezium -> Kafka -> Flink/Spark Streaming -> ClickHouse để tạo Real-time Dashboard trên Superset.
- [ ] **Task 5.4**: Áp dụng Data Quality checks (sử dụng Great Expectations hoặc Soda) dạng một bước (task) bên trong Airflow DAG.

### 6. Quản trị Dữ liệu & Siêu dữ liệu (Data Governance & Metadata)
- [ ] **Task 6.1**: Triển khai và tích hợp một công cụ Data Catalog (VD: **OpenMetadata** hoặc **DataHub** - vốn đã có cấu hình clients trong Keycloak) vào stack.
- [ ] **Task 6.2**: Cấu hình Metadata Ingestion kết nối tới Hive Metastore, ClickHouse và Kafka để tự động quét & thu thập Schema của các Tables/Topics.
- [ ] **Task 6.3**: Thiết lập **Data Lineage** (Truy vết nguồn gốc): Điền thông tin Pipeline hoặc sử dụng lineage API để mô phỏng dòng chảy dữ liệu từ Bronze -> Silver -> Gold một cách trực quan.
- [ ] **Task 6.4**: Phối hợp với Task 5.4, xây dựng Dashboard tập trung theo dõi lịch sử lỗi dữ liệu (Data Quality Trends) thay vì chỉ sinh log rỗng trong Airflow DAG.

### 7. Tối ưu CI/CD & Tài liệu hóa
- [ ] **Task 7.1**: Viết CI/CD pipelines trên GitLab CI để tự động build các custom Docker Images (nếu có update custom plugins cho Airflow/Spark).
- [ ] **Task 7.2**: Hoàn thiện bộ docs: Kiến trúc chi tiết, Data Dictionary cho dữ liệu mẫu, và cẩm nang Xử lý sự cố (Troubleshooting).

---

## Giai đoạn 2: Tiến lên Cloud-Native - Triển khai trên Kubernetes (K8s)

Giai đoạn này giúp sinh viên hiểu về hệ sinh thái Cloud-Native, cách chuyển đổi tử một ứng dụng monlithic/docker-compose sang microservices trên K8s.

### 1. Khởi tạo Infrastructure & Tools
- [ ] **Task 1.1**: Cài đặt một cluster K8s local/dev (Minikube / Kind / K3s) hoặc trên Cloud (EKS/GKE).
- [ ] **Task 1.2**: Chuẩn bị các công cụ quản lý K8s: `kubectl`, `helm`, `k9s`.
- [ ] **Task 1.3**: Triển khai Ingress Controller (Nginx Ingress / Traefik) để expose các endpoint UI (Airflow, Superset, MinIO) ra ngoài K8s.

### 2. Migration bằng Helm Charts
Thay vì tự viết manifest, sinh viên nên học cách tìm và customize Helm charts chuẩn:
- [ ] **Task 2.1**: Triển khai MinIO K8s Operator hoặc Bitnami MinIO Helm chart (cấu hình Persistent Volume Claim - PVC).
- [ ] **Task 2.2**: Triển khai Hive Metastore và PostgreSQL backing DB qua Helm.
- [ ] **Task 2.3**: Triển khai Kafka Cluster sử dụng Strimzi Kafka Operator.
- [ ] **Task 2.4**: Triển khai Spark trên K8s. (Nâng cao: Sử dụng Spark Kubernetes Operator thay vì Spark Standalone Master/Worker).
- [ ] **Task 2.5**: Triển khai Trino dùng Trino Official Helm Chart, cấu hình mount tới Hive Metastore.
- [ ] **Task 2.6**: Triển khai Airflow dùng Apache Airflow Official Helm Chart (thiết lập KubernetesExecutor thay vì CeleryExecutor).
- [ ] **Task 2.7**: Triển khai ClickHouse dùng ClickHouse Operator (Altinity).
- [ ] **Task 2.8**: Triển khai Superset và map Ingress.
- [ ] **Task 2.9**: Triển khai Data Catalog (OpenMetadata / DataHub) Helm Chart lên K8s, phân vùng dữ liệu qua PVC.

### 3. CI/CD & GitOps
- [ ] **Task 3.1**: Triển khai ArgoCD hoặc FluxCD vào cluster.
- [ ] **Task 3.2**: Cấu hình GitOps repo (chứa các file `values.yaml` và K8s manifests) để ArgoCD tự động deploy toàn bộ stack Lakehouse khi có push.

### 4. Vận hành, Security & Tự động mở rộng (Scalability) trên K8s
- [ ] **Task 4.1 (Secret Management)**: Thay thế K8s Secrets thông thường bằng External Secrets Operator (ESO) kết nối với HashiCorp Vault.
- [ ] **Task 4.2 (Observability)**: Triển khai Kube-Prometheus-Stack để monitor sức khỏe cluster và các pods + Tích hợp Promtail/Loki để gom log tập trung trên K8s.
- [ ] **Task 4.3 (Auto-scaling)**: Cấu hình Horizontal Pod Autoscaler (HPA) cho Airflow Workers hoặc Superset dựa trên CPU/Memory metrics.
- [ ] **Task 4.4 (Networking)**: Áp dụng Kubernetes Network Policies để giới hạn kết nối (ví dụ: chỉ cho phép Trino và Spark được kết nối tới Hive Metastore).

---

**Kết luận/Đánh giá Thực tập sinh:** 
Hội đồng có thể nghiệm thu dựa trên việc sinh viên:
1. Giải thích được luồng dữ liệu của một End-to-End Pipeline hoàn chỉnh.
2. Nắm vững cơ chế Fault-Tolerance và Scale-out của các framework (Kafka, Spark, Trino).
3. Đủ khả năng tự troubleshoot log khi một Pod trong K8s bị CrashLoopBackOff hoặc Out Of Memory (OOM).

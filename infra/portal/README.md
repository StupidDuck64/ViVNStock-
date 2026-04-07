# 🌐 Lakehouse Portal

## Why
Cổng truy cập tập trung cho toàn bộ nền tảng Lakehouse OSS. Giúp người dùng:
- **Đăng nhập một lần** qua Keycloak SSO (OIDC)
- **Truy cập tất cả services** từ một dashboard duy nhất, không cần nhớ `host:port`
- **Theo dõi health status** của từng dịch vụ theo real-time

## Kiến trúc Hệ thống (Architecture)

```mermaid
flowchart TD
    User([Người dùng]) -->|Truy cập :3100| Nginx[Nginx API Gateway\n:3100]
    
    sub_nginx_1(Xác thực auth_request)
    sub_nginx_2(Định tuyến tĩnh / động)
    
    Nginx --- sub_nginx_1
    Nginx --- sub_nginx_2
    
    sub_nginx_1 -->|Kiểm tra Cookie| OAuth2[OAuth2 Proxy\n:4180]
    OAuth2 -->|Chưa có Session| Keycloak[Keycloak OIDC\n:18084\nRealm: data-platform]
    
    sub_nginx_2 -->|/airflow| Airflow[Apache Airflow\nbypass: 8085]
    sub_nginx_2 -->|/minio| Minio[MinIO Console\n:9001]
    sub_nginx_2 -->|/| PortalUI[Lakehouse Portal UI\n(Tĩnh)]
    
    style Nginx fill:#f9f,stroke:#333,stroke-width:2px
    style Keycloak fill:#ff9,stroke:#333,stroke-width:2px
    style OAuth2 fill:#bbf,stroke:#333,stroke-width:2px
```

1. **Nginx API Gateway**: Xử lý toàn bộ proxy requests. Yêu cầu module `auth_request` soi cookie, block 401 nhảy trang 302 login.
2. **OAuth2 Proxy**: Middleware cho OIDC, trỏ tới issuer `data-platform` trên Keycloak để verify và redeem tokens. Đã disable aggressive JS cache.
3. **Keycloak OIDC**: Hệ thống SSO. Host được quản lý qua biến `.env` là `KEYCLOAK_HOST=127.0.0.1` để tránh lỗi đứt gãy IPv6 trên Windows (Connection Refused).
4. **Airflow 3 SPA Caveat**: Do Airflow 3.0.x dùng React SPA với `basename="/"`, việc Proxy qua Sub-path (`/airflow`) sẽ bị lỗi assets. Nginx sẽ redirect thẳng nhánh này sang Native Port `8085` và kế thừa `window.location.hostname`.
5. **Dynamic Host Resolution**: Giao diện UI sẽ tự nhận diện LAN IP / Localhost của người dùng để bind đúng domain cho từng link service. Mọi Endpoint Health-Check đều đi qua Sub-request nội bộ của Docker tránh CORS.

## How

### Khởi chạy (Độc lập / Debug)
Để chạy riêng rẽ Portal và các service phụ thuộc (Keycloak, Vault, PostgreSQL) mà không khởi chạy cả nền tảng:
```bash
docker compose --profile portal up -d
```
Portal sẽ chạy tại: **http://localhost:3100**

### Tài khoản mẫu (Keycloak)
Tài khoản SSO dùng thử được đúc sẵn trong `data-platform.json`. Tham khảo một số Role chính:
| User | Password | Role |
|------|----------|------|
| `admin` | `Admin@12345` | Platform Administrator |
| `platform-admin` | `PlatformAdmin@123` | Analytics/Superset Admin |
| `data-engineer-1` | `Engineer@123` | Data Engineering Team |

### Import Keycloak Realm (Tự Động)
Hệ thống được thiết kế hoàn toàn **Tự Động Nạp Cấu Hình**.
Khi chạy `docker compose build keycloak`, tệp JSON cấu hình `data-platform.json` sẽ được nướng thẳng vào Container.
Mỗi khi khởi tạo database mới, Keycloak sẽ tự quét file Import mà không cần thao tác bằng tay ở giao diện Admin.
*(Đảm bảo Clean volume Database `lakehouse-oss_keycloak-db` nếu cần reset mẫu Realm).*

### Thêm service mới
1. Mở `app/app.js`
2. Thêm entry vào mảng `SERVICES`
3. (Tuỳ chọn) Thêm health-check proxy vào `nginx.conf`
4. Rebuild: `docker compose build lakehouse-portal`

## Notes
- Portal hoạt động độc lập với Keycloak (graceful degradation)
- Health check chạy mỗi 30 giây
- UI hỗ trợ tìm kiếm và lọc theo category

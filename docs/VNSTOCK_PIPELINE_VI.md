# Tài Liệu Pipeline VNStock — Giải Thích Chi Tiết Bằng Tiếng Việt

> **Dành cho ai?** Tài liệu này giải thích toàn bộ hệ thống bằng ngôn ngữ đơn giản. Bạn không cần biết lập trình vẫn có thể hiểu được hệ thống làm gì, tại sao làm như vậy, và các vấn đề kỹ thuật đã được giải quyết ra sao.

---

## Mục Lục

1. [Hệ thống làm gì?](#1-hệ-thống-làm-gì)
2. [Kiến trúc tổng thể](#2-kiến-trúc-tổng-thể)
3. [Các thành phần chính](#3-các-thành-phần-chính)
4. [Hành trình của dữ liệu — từ nguồn đến người dùng](#4-hành-trình-của-dữ-liệu)
5. [Giải thích từng vấn đề kỹ thuật](#5-giải-thích-từng-vấn-đề-kỹ-thuật)
6. [Dữ liệu hiện có](#6-dữ-liệu-hiện-có)
7. [Hướng dẫn vận hành](#7-hướng-dẫn-vận-hành)

---

## 1. Hệ Thống Làm Gì?

Hệ thống này là một **Data Lakehouse** (kho dữ liệu) chuyên thu thập, lưu trữ và phục vụ dữ liệu **giá chứng khoán Việt Nam** theo thời gian thực và lịch sử.

Hãy nghĩ đến nó như một **thư viện cổ phiếu**:
- **Thu thập**: Tự động lấy giá cổ phiếu từ nhiều nguồn (DNSE, VCI) mỗi phút hoặc mỗi ngày
- **Lưu trữ**: Lưu vào kho có cấu trúc, có thể truy vấn nhanh
- **Phục vụ**: Cung cấp API để frontend (biểu đồ TradingView) hiển thị lên màn hình

**Quy mô hiện tại:**
- ~1,012 mã chứng khoán (HOSE, HNX, UPCOM, Phái sinh, Index)
- 11 năm dữ liệu nến ngày (2015–2026)
- 2.5 năm dữ liệu nến 1 phút (2023–2026)
- Khoảng **135+ triệu bản ghi** sau khi backfill hoàn thành

---

## 2. Kiến Trúc Tổng Thể

```
┌─────────────────────────────────────────────────────────────┐
│                    NGUỒN DỮ LIỆU                            │
│  DNSE API ──────────────────────▶  Nến ngày (1D)             │
│  (services.entrade.com.vn)       Lịch sử từ 2015             │
│                                                              │
│  VCI API ───────────────────────▶  Nến 1 phút (1M)           │
│  (trading.vietcap.com.vn)        Lịch sử 2.5 năm             │
└──────────────────────┬──────────────────────────────────────┘
                       │ (HTTP fetch)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  TẦNG XỬ LÝ (SPARK)                         │
│                                                              │
│   Spark Worker 1 ──┐                                        │
│   Spark Worker 2 ──┤──▶ backfill_1d.py / backfill_1m.py     │
│   Spark Master ────┘    (song song 20 symbol/lần)            │
└──────────────────────┬──────────────────────────────────────┘
                       │ (ghi vào Iceberg)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              TẦNG LƯU TRỮ (ICEBERG + MinIO + Hive)          │
│                                                              │
│   MinIO (object store, giống S3)                             │
│     └── s3a://iceberg/warehouse/                             │
│            ├── bronze/vnstock_ohlc_1d/    (2M rows)         │
│            ├── bronze/vnstock_ohlc_1m/    (130M rows)       │
│            ├── bronze/vnstock_ohlc_5m/                      │
│            ├── bronze/vnstock_ohlc_15m/                     │
│            ├── bronze/vnstock_ohlc_30m/                     │
│            ├── bronze/vnstock_ohlc_1h/                      │
│            └── bronze/vnstock_ohlc_4h/                      │
│                                                              │
│   Hive Metastore (lưu schema/metadata)                       │
│   Trino (SQL query engine)                                   │
└──────────────────────┬──────────────────────────────────────┘
                       │ (Trino SQL / REST API)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              TẦNG PHỤC VỤ                                    │
│                                                              │
│   FastAPI / vnstock-api ──▶ /api/history?symbol=VCB&...      │
│   Redis Cache             ──▶ 1st call: ~500ms               │
│                              2nd call (cached): ~10ms         │
│                                                              │
│   vnstock-frontend (React) ──▶ Biểu đồ TradingView           │
└─────────────────────────────────────────────────────────────┘
                       ▲
                       │
┌──────────────────────┴──────────────────────────────────────┐
│              ĐIỀU PHỐI (AIRFLOW)                             │
│                                                              │
│   DAG: vnstock_backfill_1m_daily  (01:00 ICT mỗi ngày)       │
│   DAG: vnstock_backfill_1d_weekly (02:00 ICT mỗi Chủ Nhật)  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Các Thành Phần Chính

### 3.1. Nguồn Dữ Liệu

| Nguồn | Loại dữ liệu | Chiều sâu lịch sử | Giới hạn |
|-------|-------------|-------------------|---------|
| **DNSE** (services.entrade.com.vn) | Nến ngày (1D) | Từ 2015 | Cần API Key |
| **DNSE** (services.entrade.com.vn) | Nến 1 phút (1M) | 90 ngày | Cần API Key |
| **VCI** (trading.vietcap.com.vn) | Nến 1 phút (1M) | ~2.5 năm | Không cần đăng nhập |

> **Tại sao cần 2 nguồn?** DNSE chỉ có 90 ngày nến 1 phút, không đủ để phân tích kỹ thuật trung/dài hạn. VCI có đến 2.5 năm, đủ cho phân tích chiến lược.

### 3.2. Spark (Bộ xử lý dữ liệu)

Apache Spark là engine xử lý dữ liệu phân tán. Hãy tưởng tượng nó như một **nhà máy với nhiều dây chuyền song song**:
- **Spark Master**: Quản lý, phân công công việc
- **Spark Worker 1, 2**: Thực thi thực tế (mỗi worker có 4 CPU cores, 4GB RAM)
- **Container memory limit**: Master chỉ có **1GB** → quan trọng (xem phần 5)

### 3.3. Iceberg (Định dạng bảng dữ liệu)

Apache Iceberg là "hệ thống tập tin thông minh" cho dữ liệu lớn:
- **ACID transactions**: Mỗi lần ghi là một "snapshot" mới, tránh lỗi khi ghi song song
- **Schema evolution**: Có thể thêm cột mà không cần rebuild toàn bộ bảng
- **Time travel**: Có thể query dữ liệu ở thời điểm quá khứ
- **Parquet format**: Dữ liệu được nén hiệu quả, đọc nhanh theo cột

### 3.4. MinIO (Lưu trữ vật lý)

MinIO là **phiên bản tự host của Amazon S3**. Dữ liệu thực sự nằm trong các file Parquet trên MinIO, tổ chức theo cấu trúc:
```
s3://iceberg/warehouse/
  bronze.db/
    vnstock_ohlc_1m/
      data/          ← các file .parquet thực sự
      metadata/      ← Iceberg metadata, snapshots
```

### 3.5. Airflow (Bộ lên lịch)

Apache Airflow tự động hóa các pipeline theo lịch:
- **DAG** (Directed Acyclic Graph) = một quy trình công việc có thứ tự
- Mỗi ngày lúc 01:00 ICT → Airflow tự kích hoạt job Spark lấy dữ liệu 1M mới
- Mỗi Chủ Nhật lúc 02:00 ICT → Airflow chạy lại backfill toàn bộ nến ngày

### 3.6. Trino (SQL Query Engine)

Trino là công cụ cho phép truy vấn SQL trực tiếp vào các bảng Iceberg trên MinIO:
```sql
-- Ví dụ query qua Trino
SELECT symbol, close, time
FROM iceberg.bronze.vnstock_ohlc_1m
WHERE symbol = 'VCB'
  AND time > 1700000000000
ORDER BY time DESC LIMIT 100;
```

---

## 4. Hành Trình Của Dữ Liệu

### 4.1. Backfill Lịch Sử (Một Lần Duy Nhất)

Đây là quá trình "nạp dữ liệu ban đầu" — lấy toàn bộ lịch sử từ quá khứ.

**Bước 1: Lấy danh sách mã chứng khoán**
```
symbols.txt → 1,012 mã (VCB, HPG, FPT, VNM, ...)
```

**Bước 2: Script gọi API để lấy OHLCV**

Mỗi nến bao gồm:
- **O** (Open): Giá mở cửa
- **H** (High): Giá cao nhất
- **L** (Low): Giá thấp nhất
- **C** (Close): Giá đóng cửa
- **V** (Volume): Khối lượng giao dịch
- **T** (Time): Thời điểm (Unix timestamp milliseconds)

**Bước 3: Xử lý và chuẩn hóa**
- VCI trả về giá full VND (ví dụ: 57,700) → chia cho 1000 → 57.7 (đơn vị nghìn đồng, khớp DNSE)
- Timestamp VCI là Unix giây dạng string → nhân 1000 → milliseconds

**Bước 4: Ghi vào Iceberg theo lô (batch)**
- Mỗi batch = 5 mã (để tránh tràn bộ nhớ driver 1GB)
- Batch đầu: `createOrReplace` (tạo mới hoặc thay thế bảng)
- Batch tiếp theo: `append` (chèn thêm)

**Bước 5: Tạo các khung thời gian phái sinh**
- Từ bảng 1M → tính 5M, 15M, 30M, 1H, 4H bằng Spark SQL aggregation
- Cách tính: nhóm các nến 1 phút theo bucket thời gian, lấy open đầu, high cao nhất, low thấp nhất, close cuối, volume tổng

### 4.2. Dữ Liệu Streaming Thời Gian Thực

Ngoài backfill, hệ thống cũng có pipeline real-time:
```
Nguồn thời gian thực → Kafka → Flink/Spark Streaming → Iceberg
```
Tuy nhiên phần này chưa được kích hoạt đầy đủ trong giai đoạn hiện tại.

### 4.3. Phục Vụ API

Khi frontend yêu cầu dữ liệu biểu đồ:
```
Trình duyệt → vnstock-frontend (React)
           → /api/history?symbol=VCB&interval=1m&limit=500
           → vnstock-api (FastAPI + Redis Cache)
           → Trino SQL → Iceberg (MinIO)
           ← JSON response: [{time, open, high, low, close, volume}, ...]
           ← Biểu đồ TradingView hiển thị
```

---

## 5. Giải Thích Từng Vấn Đề Kỹ Thuật

Phần này giải thích chi tiết các vấn đề thực tế đã gặp trong quá trình xây dựng, và cách giải quyết từng vấn đề một.

---

### Vấn Đề #1: Nguồn DNSE Chỉ Có 90 Ngày Dữ Liệu 1M

**Vấn đề là gì?**

Khi bắt đầu backfill dữ liệu nến 1 phút, chúng ta dùng DNSE API. Sau khi chạy xong mới phát hiện: DNSE chỉ lưu lịch sử **tối đa 90 ngày** cho nến 1 phút. Điều này có nghĩa là người dùng chỉ xem được nến 1 phút trong vòng 3 tháng gần nhất — quá ngắn để phân tích xu hướng.

**Mục tiêu:** Cần ít nhất 1 năm, lý tưởng là 3 năm.

**Giải pháp:**

Tìm nguồn dữ liệu thay thế. Sau khi khảo sát:

| Nguồn thử | Kết quả |
|-----------|---------|
| DNSE | ❌ Chỉ 90 ngày 1M |
| TCBS | ❌ API 404 (đã bị deprecated) |
| vnstock library | ❌ Bị giới hạn rate (20 req/phút, tự tắt process) |
| **VCI direct API** | ✅ **2.5 năm, không cần đăng nhập** |

**Cách tìm ra VCI API:**

Chúng ta đọc source code thư viện `vnstock3` trong container Spark, tìm file `vnstock3/explorer/vci/const.py`. File này chứa endpoint mà thư viện dùng nội bộ:
```
https://trading.vietcap.com.vn/api/chart/OHLCChart/gap
```

Thay vì dùng qua thư viện (bị rate limit), chúng ta gọi thẳng endpoint này qua HTTP.

**Kết quả:** VCI cung cấp 2.5 năm dữ liệu (tháng 10/2023 → hiện tại) cho tất cả mã chứng khoán.

---

### Vấn Đề #2: Định Dạng Giá VCI Khác DNSE

**Vấn đề là gì?**

Khi so sánh dữ liệu: DNSE trả về giá VCB là `57.7`, nhưng VCI trả về `57700`. Nếu không xử lý, biểu đồ sẽ hiển thị sai hoặc không khớp khi chuyển đổi giữa hai nguồn.

**Nguyên nhân:**
- DNSE: đơn vị **nghìn đồng** (57.7 = 57,700 VND)
- VCI: đơn vị **đồng** (57700 = 57,700 VND)
- Tỷ lệ chênh lệch: **1,000 lần**

**Giải pháp:**

Trong hàm `fetch_vci()`, chia tất cả giá cho 1000 trước khi lưu:
```python
"open":  float(v) / 1000.0,   # 57900 → 57.9
"high":  float(v) / 1000.0,   # 58500 → 58.5
"low":   float(v) / 1000.0,   # 57600 → 57.6
"close": float(v) / 1000.0,   # 57700 → 57.7
```

Đồng thời, VCI trả về timestamp dạng **chuỗi ký tự giây** (`"1774836900"`), cần chuyển sang **số nguyên milliseconds**:
```python
"time": int(t) * 1000,   # "1774836900" → 1774836900000
```

**Xác minh:** So sánh cuối bảng từ cả hai nguồn khớp hoàn toàn:
```
DNSE VCB close[-1] = 57.7  ✓
VCI  VCB close[-1] = 57700 / 1000 = 57.7  ✓
```

---

### Vấn Đề #3: Thư Viện `vnstock` Tự Tắt Process Khi Gọi Quá Nhiều

**Vấn đề là gì?**

Lần đầu dùng `vnstock` library thay vì direct HTTP, job bị dừng đột ngột sau vài request với thông báo "Rate limit exceeded. Process terminated." Không có stack trace, không có lỗi — chỉ bị tắt thẳng.

**Nguyên nhân kỹ thuật:**

`vnstock` (phiên bản mới) phụ thuộc vào gói `vnai`. Gói `vnai` này hoạt động như một "middleware" chen vào tất cả HTTP request. Khi phát hiện quá 20 request/phút (ngưỡng của gói miễn phí), nó gọi `sys.exit()` — tức là **tự tắt toàn bộ Python process**, không thể catch bằng try/except thông thường.

**Giải pháp:**

Bỏ hoàn toàn dependency vào `vnstock` library. Thay vào đó, gọi thẳng HTTP đến VCI API:

```python
# THAY VÌ (bị rate limit, tự tắt):
from vnstock import Vnstock
stock = Vnstock().stock(symbol="VCB", source="VCI")
df = stock.quote.history(...)

# DÙNG CÁCH NÀY (không limit, không dependency):
import requests
response = requests.post(
    "https://trading.vietcap.com.vn/api/chart/OHLCChart/gap",
    json={"timeFrame": "ONE_MINUTE", "symbols": ["VCB"], "from": ..., "to": ...},
    headers={"Origin": "https://trading.vietcap.com.vn/", ...}
)
```

Cũng đã gỡ bỏ `vnstock`, `vnstock3`, `vnai` khỏi container Spark:
```bash
pip uninstall vnstock vnstock3 vnai -y
```

---

### Vấn Đề #4: Script Bash Bị PowerShell Biến Đổi Nội Dung

**Vấn đề là gì?**

Trong nhiều lần chạy, các script bash được tạo như sau:
```powershell
docker exec container bash -c "cat > /tmp/script.sh << 'HEREDOC'
...nội dung...
HEREDOC"
```

Kết quả: Script bị "hỏng" — một số biến bị mất, một số biến bị thay bằng giá trị sai. Job Spark khởi động rồi chết im lặng sau 40 giây (EXIT=137).

**Nguyên nhân kỹ thuật:**

PowerShell (Windows) **diễn giải** nội dung của chuỗi trước khi gửi vào Docker:

| Ký hiệu | Ý nghĩa trong Bash | Bị PowerShell xử lý thành |
|---------|-------------------|--------------------------|
| `$(date)` | Gọi lệnh `date` trong bash | Gọi `Get-Date` → hardcode ngày giờ Windows |
| `$JARS` | Biến bash `$JARS` | Tìm biến PowerShell `$JARS` → chuỗi rỗng |
| `$?` | Exit code của lệnh trước | `True` (kiểu boolean PowerShell) |

Kết quả là `--jars $JARS` trong script trở thành `--jars ` (rỗng). Spark chạy không có Iceberg JARs → không ghi được vào Iceberg → `total_rows=0` → thoát bình thường (EXIT=0, không báo lỗi).

**Giải pháp:**

Tạo file script **trực tiếp trên máy Windows** sử dụng công cụ `create_file`, rồi copy vào container bằng `docker cp`. Cách này hoàn toàn bỏ qua PowerShell:

```powershell
# Tạo file locally (không có PowerShell expansion)
create_file("infra/spark/run_backfill_1m_900d.sh", content="""...""")

# Copy vào container (direct binary copy, không xử lý nội dung)
docker cp infra/spark/run_backfill_1m_900d.sh container:/tmp/
```

Toàn bộ JAR paths được **hardcode trực tiếp** trong script (không dùng biến):
```bash
--jars /opt/bitnami/spark/jars/iceberg-spark-runtime-3.5_2.12-1.9.2.jar,...
```

---

### Vấn Đề #5: Driver Memory 6GB — Container Chỉ Có 1GB

**Vấn đề là gì?**

Sau khi sửa script PowerShell, job vẫn chết sau 40 giây với `EXIT=137`. 
`EXIT=137` trong Linux = **SIGKILL** = bị Operating System cưỡng bức tắt do hết RAM.

**Nguyên nhân:**

Script cấu hình `--driver-memory 6G`, nghĩa là yêu cầu Spark driver (chạy trong container spark-master) dùng 6GB RAM. Nhưng khi kiểm tra:

```
docker inspect spark-master-1 --format '{{.HostConfig.Memory}}'
→ 1073741824  (= 1GB)
```

Container spark-master bị giới hạn **chỉ 1GB** trong docker-compose. Khi JVM cố khởi động với heap 6GB trong container 1GB → hệ điều hành dùng OOM Killer tắt ngay lập tức (thường trong 40 giây).

**Bộ nhớ của từng container:**
- `spark-master-1`: **1GB** (chỉ làm điều phối, không xử lý data)
- `spark-worker-1-1`: **4GB** (xử lý data, chạy executor)
- `spark-worker-2-1`: **4GB** (xử lý data, chạy executor)

**Giải pháp:**

```bash
# TRƯỚC (bị kill):
--driver-memory 6G   # Driver chạy trong spark-master (1GB container) → OOM
--batch-size 50      # 50 mã × 130K rows = 6.5M rows/batch → cần nhiều RAM

# SAU (hoạt động tốt):
--driver-memory 600M  # Driver dùng ≤600MB → vừa đủ trong container 1GB
--batch-size 5        # 5 mã × 130K rows = 650K rows/batch → ~50MB RAM
```

Nguyên tắc: **Driver** (spark-master) chỉ cần điều phối — không cần nhiều RAM. **Executor** (spark-worker) mới là nơi xử lý data nặng → có thể dùng nhiều RAM hơn.

**Xác minh:** Test với 5 mã chứng khoán:
```
5 symbols → 649,153 rows → 49 giây → EXIT=0 ✓
```

---

### Vấn Đề #6: Tổng Hợp Nến (Aggregation) Từ 1M Lên Các Khung Thời Gian Cao Hơn

**Vấn đề là gì?**

Frontend cần hiển thị nến 5M, 15M, 30M, 1H, 4H. Nhưng chúng ta chỉ có dữ liệu gốc 1M từ VCI. Không thể tải từng khung thời gian riêng từ API (chậm, không nhất quán).

**Giải pháp: Tự tính từ dữ liệu 1M**

Từ 5 nến 1 phút → ghép lại thành 1 nến 5 phút theo quy tắc:

```
Thời điểm 09:30 (~5 nến 1M):
  09:30 O=57.5, H=57.6, L=57.4, C=57.5, V=100K
  09:31 O=57.5, H=57.7, L=57.4, C=57.6, V=120K
  09:32 O=57.6, H=57.8, L=57.5, C=57.7, V=80K
  09:33 O=57.7, H=57.9, L=57.6, C=57.8, V=150K
  09:34 O=57.8, H=58.0, L=57.7, C=57.9, V=200K

→ Nến 5M tại 09:30:
  O=57.5  (open của nến đầu tiên)
  H=58.0  (high cao nhất)
  L=57.4  (low thấp nhất)
  C=57.9  (close của nến cuối cùng)
  V=650K  (volume tổng cộng)
```

**Cách thực hiện kỹ thuật:**

Spark SQL `FLOOR` function chuyển mỗi timestamp về "bucket" thời gian:
```python
ms = 5 * 60 * 1000  # 5 phút = 300,000 milliseconds
time_bucket = floor(time / ms) * ms   # làm tròn xuống về đầu bucket
```

Sau đó `GROUP BY (symbol, time_bucket)` và tính các giá trị OHLCV.

Cách đặc biệt để lấy đúng open/close (không phải min/max):
- `open`: lấy giá trị tại timestamp **nhỏ nhất** trong bucket
- `close`: lấy giá trị tại timestamp **lớn nhất** trong bucket
```python
min(struct("time", "open")).getField("open")   # open của nến đầu
max(struct("time", "close")).getField("close") # close của nến cuối
```

---

## 6. Dữ Liệu Hiện Có

### Trạng Thái Ngày 07/04/2026

| Bảng | Trạng thái | Số hàng | Số mã | Ghi chú |
|------|-----------|---------|-------|---------|
| `vnstock_ohlc_1m` | ✅ Hoạt động | 39,009+ | 763 | Backfill 07/04/2026 + Batch Layer đang ghi |
| `vnstock_ohlc_5m` | ✅ Derived | - | - | Re-aggregate từ 1m |
| `vnstock_ohlc_15m` | ✅ Derived | - | - | Re-aggregate từ 1m |
| `vnstock_ohlc_1h` | ✅ Derived | - | - | Re-aggregate từ 1m |
| `vnstock_ohlc_4h` | ✅ Derived | - | - | Re-aggregate từ 1m |
| `vnstock_ohlc_1d` | ⚠️ Chưa có | 0 | 0 | Cần chạy `backfill_1d.py` |

> **Real-time:** Speed Layer WebSocket đang stream tick-by-tick từ DNSE, ghi vào Redis + Kafka liên tục.  
> **Lịch sử:** Cần chạy thêm backfill nhiều ngày để có đủ dữ liệu phân tích kỹ thuật.

---

## 7. Hướng Dẫn Vận Hành

### 7.1. Kiểm tra tiến độ backfill 1M (đang chạy)

```powershell
docker exec lakehouse-oss-vuongngo-spark-master-1 bash -c "grep 'progress' /tmp/backfill_1m_900d.log | tail -5"
```

Kết quả mẫu:
```
Fetch+write progress: 500/1012 (ok=498 fail=2 rows_so_far=64M elapsed=1620s)
```

### 7.2. Xem toàn bộ dữ liệu hiện có

```powershell
docker exec lakehouse-oss-vuongngo-trino-1 trino --execute "
SELECT
  table_name as tbl,
  'query needed' as rows
FROM iceberg.information_schema.tables
WHERE table_schema = 'bronze'
ORDER BY table_name
" 2>&1
```

### 7.3. Đếm số hàng và phạm vi ngày

```powershell
docker exec lakehouse-oss-vuongngo-trino-1 trino --execute "
SELECT '1m' as res, COUNT(*) as rows, COUNT(DISTINCT symbol) as syms,
  DATE(FROM_UNIXTIME(MIN(time)/1000)) as earliest,
  DATE(FROM_UNIXTIME(MAX(time)/1000)) as latest
FROM iceberg.bronze.vnstock_ohlc_1m
UNION ALL
SELECT '1d', COUNT(*), COUNT(DISTINCT symbol),
  DATE(FROM_UNIXTIME(MIN(time)/1000)),
  DATE(FROM_UNIXTIME(MAX(time)/1000))
FROM iceberg.bronze.vnstock_ohlc_1d
" 2>&1
```

### 7.4. Chạy lại backfill thủ công (nếu cần)

```powershell
# Copy script mới nhất vào container
docker cp "infra/spark/run_backfill_1m_900d.sh" lakehouse-oss-vuongngo-spark-master-1:/tmp/

# Chạy background
docker exec -d lakehouse-oss-vuongngo-spark-master-1 bash -c "/tmp/run_backfill_1m_900d.sh > /tmp/backfill_1m_900d.log 2>&1"

# Xem log
docker exec lakehouse-oss-vuongngo-spark-master-1 bash -c "tail -f /tmp/backfill_1m_900d.log"
```

### 7.5. Cấu hình tài nguyên Spark

| Job | Driver Memory | Executor Memory | Executor Cores | Num Executors |
|-----|-------------|----------------|---------------|--------------|
| Backfill 1M (lần này) | 600M | 3G | 4 | 2 |
| Backfill 1M (scheduled) | 2G | 2G | 1 | 1 |
| Backfill 1D (scheduled) | 2G | 2G | 1 | 1 |

> **Lý do khác nhau:** Lần backfill lịch sử này cần nhanh → dùng nhiều core. Scheduled hàng ngày chỉ cần update incremental nhỏ → 1 core đủ, để tài nguyên cho các service khác.

### 7.6. Các lỗi thường gặp và cách xử lý

| Triệu chứng | Nguyên nhân | Giải pháp |
|-------------|-------------|-----------|
| EXIT=137 | Container OOM / driver-memory quá lớn | Giảm `--driver-memory`, kiểm tra container limit |
| EXIT=0 nhưng 0 rows | JAR paths sai → không có Iceberg | Dùng hardcoded JAR paths, không dùng biến `$JARS` |
| "Rate limit exceeded" | `vnai` package can thiệp | Gỡ vnstock/vnai, dùng VCI direct API |
| "VCI no data for XXX" | Mã không niêm yết trên HOSE/HNX | Bình thường, fallback DNSE |
| Trino query timeout | Quá nhiều small files | Chạy `EXECUTE optimize` cho bảng |

---

*Tài liệu được cập nhật ngày 07/04/2026 — phản ánh kiến trúc Hybrid Producer mới.*

![Vivnstock.png](attachment:fbb18ab6-8969-44e5-800d-e97e17a502d7:Vivnstock.png) 
# Mô tả dự án

- **Yêu cầu tính năng**
    
    Cung cấp dữ liệu giá chứng khoán của các mã chứng khoán và các chỉ số thị trường theo thời gian thực từ các sàn HNX, HOSE, UPCOM (khoảng 1000 mã)
    
    Người dùng có thể xem dữ liệu quá khứ của các mã này, với các timeframe 1→1h đặt retension 90 ngày, quá 90 ngày chỉ có timeframe 1d
    
    Cung cấp các thông tin mang tính tổng hợp, ví dụ như bảng xếp hạng các mã cổ phiếu tăng mạnh nhất, giảm mạnh nhất, nhóm ngành tăng nhiều nhất trong 1 khoảng thời gian cụ thể
    
    Cung cấp 1 cửa sổ nhỏ gồm các tin tức từ chính trị, tài chính từ CafeF, Vietstock, VnEconomy
    
    [Optional] Mô hình chatbot cung cấp lời khuyên với các mã chứng khoán dựa vào phân tích kỹ thuật giá lịch sử
    
- **Data platform**
    - [ ]  Config Kafka, tạo các topic và Schema-registry cho dữ liệu từ DNSE market websocket
    - [ ]  Config MinIO làm S3 Storage backend cho Iceberg (tạo các bucket: `bronze`, `silver`, `gold`)
    - [ ]  Triển khai KeyDB (Multi-threaded Redis) để lưu trữ State và phục vụ caching cho Real-time data.
    - [ ]  Thiết lập Monitoring Stack: Prometheus + Grafana để track Kafka lag và RAM/CPU của cụm Spark
    - [ ]  Cấu hình logging tập trung với Elasticsearch+Logstash+Kibana
    
- **Các job data cần thiết kế**
    - [ ]  *[src/producer]* Viết script Python producer nhận dữ liệu từ DNSE websocket đổ vào Kafka topic
    - *src/producer]* Viết script Python producer nhận dữ liệu từ DNSE websocket đổ vào Kafka topic
    - Lấy dữ liệu từ `Security Definition` làm mốc tham chiếu để tính toán các chỉ số trong ngày, vì đây là dữ liệu chỉ gửi 1 lần duy nhất, cân nhắc dùng API thay vì websocket.
    
    <aside>
    💡
    
    > Cung cấp thông tin về giá trần sàn tham chiếu và trạng thái của mã chứng khoán trong ngày giao dịch. Dữ liệu được hệ thống gửi một lần duy nhất vào 8h sáng đầu ngày giao dịch.
    > 
    </aside>
    
    - Với dữ liệu giá, sử dụng `OHLC` để vẽ nến realtime, các loại dữ liệu sẽ lấy gồm Stock, Derivative và Index, time frame lấy chỉ bao gồm nến 1m, chia dữ liệu này ra làm 3 topic riêng `ohlc_stock` , `ohlc_derivative` và `ohlc_index` . Insert thêm trường `source` và `ingest_timestamp` để truy xuất nguồn dữ liệu và khâu check data quality và sử dụng Avro Serialization để nén data lại.
    - Lấy dữ liệu từ `Quote` để làm bảng độ sâu thị trường gồm các giá chào mua và chào bán tốt nhất thị trường, thường thì 3 mức giá cho mua và bán là được, HNX với UPCOM thì hỗ trợ lên đến 10 mức giá.
    - Nhận dữ liệu `Expected price` để có thông tin giá đóng cửa, giá khớp dự kiến và khối lượng khớp dự kiến của mã chứng khoán trong các phiên giao dịch khớp lệnh định kỳ ATO và ATC, gắn flag `is_expected=True` để Frontend biết đường mà hiển thị giá dự khớp..
    - [ ]  *[src/streaming]*  Viết script PySpark streaming data từ Kafka topic vào KeyDB phục vụ dữ liệu realtime và 1 luồng check point xuống MinIO
    - [ ]  *[src/batch]*  Viết sript PySpark xử lý dữ liệu từ Kafka topic, sử dụng Iceberg table format để lưu dữ liệu xuống `bronze` bucket
    - [ ]  *[src/hisbackfill_1m]*  Viết script kéo dữ liệu lịch sử timeframe 1m, retension 90 ngày cho tất cả các mã chứng khoán, DNSE API limit 100 request/1h và 1000 request/1d nên cần set lịch chạy Airflow cho phù hợp
    - [ ]  *[src/hisbackfill_1d]*  Viết script kéo dữ liệu lịch sử timeframe 1d, retention dài nhất có thể đối với từng mã chứng khoán, có thể lấy dữ liệu từ thư viện vnstock3, dữ liệu từ vnstock3 không có limit request, có thể schedule Airflow chạy liên tục.
    - [ ]  *[src/compact]*  Viết script compact các file nhỏ trong `bronze` bucket, để mỗi file lưu trữ giá của đúng 1 mã chứng khoán trong tầng `silver`
    - [ ]  *[src/aggrigate]*  Viết script tổng hợp dữ liệu trong tầng silver thành các dữ liệu có tính chất tổng hợp, xếp hạng trong tầng `gold`
    - [ ]  *[src/new_crawler]*  Thiết kế news crawler, lấy tiêu đề các bài báo và link bài báo từ  CafeF, Vietstock, VnEconomy
- **Thiết kế back-end**
    - [ ]  *WebSocket Server:* Tiếp nhận kết nối từ Front-end và đẩy giá nhảy (Push mechanism) từ KeyDB qua WebSocket.
    - [ ]  *Historical API:* Endpoint truy vấn dữ liệu quá khứ từ Iceberg (hỗ trợ phân trang và chọn timeframe).
    - [ ]  *Analytics API:* Cung cấp dữ liệu bảng xếp hạng và biến động nhóm ngành đã được tính toán sẵn.
    - [ ]  *News API:* Endpoint trả về danh sách tin tức theo định dạng JSON cho Front-end hiển thị.
    - [ ]  *Chatbot Service (Optional):* Sử dụng dữ liệu đã thu thập từ tầng để đọc dữ liệu từ Gold layer và đưa ra nhận định kỹ thuật.
- **Thiết kế front-end**
    - [ ]  *Market List&Dashboard:* List các mã chứng khoán theo thứ tự A→Z và bảng giá chứng khoán dạng nến khi nhấn vào 1 mã cụ thể hiển thị theo thời gian thực .
    - [ ]  *Chart Component:* Tích hợp thư viện TradingView Lightweight Charts để vẽ nến 1m, 5m, 15m, 1h, 1d từ dữ liệu lịch sử.
    - [ ]  *Aggregated Widget*: Component hiển thị Top 10 mã tăng/giảm mạnh nhất và Heatmap nhóm ngành.
    - [ ]  *News Sidebar*: Cửa sổ tin tức cập nhật liên tục với nguồn dữ liệu từ các nguồn bên ngoài.
    - [ ]  *Chatbot Interface*: Cửa sổ chat nhỏ góc màn hình để người dùng hỏi đáp về kỹ thuật mã chứng khoán.
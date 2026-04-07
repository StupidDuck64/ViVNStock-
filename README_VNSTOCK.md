# VVS Data Lakehouse (Vietnam Vantage Securities)

> **Real-time Vietnamese Stock Market Platform** — Lambda Architecture on 100% Open-Source Stack
>
> Collects, processes, stores, and visualizes data for **1012 stock symbols** on the Vietnamese market
> (HOSE 403 + HNX 296 + UPCOM 300 + 9 Index + 4 Derivatives) in real-time,
> using a Lambda Architecture combining a Batch Layer (Iceberg) and a Speed Layer (Kafka + Redis).

[![Spark](https://img.shields.io/badge/Spark-3.5.6-orange?logo=apachespark)](https://spark.apache.org/)
[![Kafka](https://img.shields.io/badge/Kafka-KRaft-black?logo=apachekafka)](https://kafka.apache.org/)
[![Iceberg](https://img.shields.io/badge/Iceberg-1.9.2-blue)](https://iceberg.apache.org/)
[![Docker](https://img.shields.io/badge/Docker-13%2B_Services-blue?logo=docker)](https://docs.docker.com/compose/)
[![React](https://img.shields.io/badge/React-18.3-61DAFB?logo=react)](https://reactjs.org/)

---

## System Architecture

```
                          VVS Data Lakehouse — Lambda Architecture

  ┌──────────────┐                ┌──────────────┐         ┌──────────────┐
  │  DNSE REST   │  HTTP polling  │   Producer   │  JSON   │    Kafka     │
  │  API (1012   │ ─────────────► │  (Python)    │ ──────► │  (KRaft)     │
  │  symbols)    │  every 15s     │  50 workers  │  lz4    │  1 topic     │
  └──────────────┘                └──────┬───────┘         └──────┬───────┘
                                         │ simultaneous           │
                                         ▼                        ▼
                                  ┌──────────────┐    ┌───────────────────────┐
                                  │    Redis     │    │  PySpark Structured   │
                                  │  (tick cache)│    │  Streaming            │
                                  └──────┬───────┘    │  (foreachBatch)       │
                                         │            │  ┌─────────────────┐  │
                        ┌────────────────┤            │  │ Iceberg append  │  │
                        │                │            │  │ + Redis update  │  │
                        ▼                ▼            │  └─────────────────┘  │
                 ┌──────────────┐ ┌──────────────┐    └───────────┬───────────┘
                 │   FastAPI    │ │   FastAPI    │                │
                 │  WebSocket   │ │  REST API   │                ▼
                 │ /api/ws/     │ │ /api/history │    ┌───────────────────────┐
                 │  stream      │ │ /api/realtime│    │   Apache Iceberg      │
                 └──────┬───────┘ └──────┬───────┘    │   (on MinIO S3)       │
                        │                │            │  ┌───────┬──────────┐ │
                        ▼                ▼ via Trino  │  │Bronze │  Gold    │ │
                 ┌──────────────────────────────┐     │  │ 1m-4h │  1d     │ │
                 │       React Frontend          │     │  └───────┴──────────┘ │
                 │  Lightweight Charts (TV-style)│     └───────────────────────┘
                 │  SMA 20 + EMA 50 + Volume     │
                 └──────────────────────────────┘

                 ┌──────────────────────────────┐     ┌───────────────────────┐
                 │  MONITORING                   │     │   Airflow             │
                 │  Prometheus → Grafana          │     │  Backfill 1m / 1d    │
                 │  Promtail  → Loki              │     │  Compact Bronze→Slvr │
                 │  cAdvisor + Node Exporter      │     │  News Crawler        │
                 └──────────────────────────────┘     └───────────────────────┘
```

### Data Flow Summary

| Layer | Component | Role |
|-------|-----------|------|
| **Ingestion** | DNSE REST API → Producer → Kafka + Redis | Poll 1012 symbols every 15s with 50 concurrent workers |
| **Speed Layer** | PySpark Structured Streaming: Kafka → Iceberg + Redis | Persist real-time ticks to Iceberg, update Redis for frontend |
| **Batch Layer** | PySpark Batch: DNSE REST → Iceberg (backfill) | Historical 1m (90 days) + 1d (from 2015) + auto-aggregate 5m/15m/30m/1h/4h |
| **Serving Layer** | FastAPI + Trino + Redis | Historical candles from Iceberg via Trino, real-time ticks from Redis |
| **Presentation** | React + Lightweight Charts + WebSocket | TradingView-style charting with hybrid history + real-time |
| **Orchestration** | Airflow (SparkSubmitOperator) | Schedule backfill, compaction, news crawling |
| **Monitoring** | Prometheus + Grafana + Loki + Promtail | Pipeline monitoring: Kafka lag, RAM, CPU, container logs |

---

## Tech Stack

| Category | Technology | Version | Role |
|----------|-----------|---------|------|
| **Message Broker** | Apache Kafka (KRaft) | 3.5.x | JSON message bus, no ZooKeeper |
| **Stream Processing** | Apache Spark (PySpark) | 3.5.6 | Structured Streaming + Batch ETL |
| **Table Format** | Apache Iceberg | 1.9.2 | ACID on S3, time-travel, schema evolution |
| **Object Storage** | MinIO | Latest | S3-compatible storage for Iceberg |
| **Query Engine** | Trino | Latest | Distributed SQL over Iceberg tables |
| **Orchestration** | Apache Airflow | 2.10.x | DAG scheduling, backfill, compaction |
| **Cache** | Redis | 7.2 | Real-time tick/quote serving |
| **API Backend** | FastAPI + Uvicorn | 0.115+ | REST + WebSocket, GZip compression |
| **Frontend** | React 18 + Lightweight Charts 5 | 18.3.1 | TradingView-style UI, SMA/EMA indicators |
| **Data Source** | DNSE REST API | — | Vietnamese stock market data (no rate limit with API key) |

---

## Symbol Coverage — 1012 Symbols

| Exchange | Count | Description |
|----------|-------|-------------|
| **HOSE** | 403 | All stocks on Ho Chi Minh Stock Exchange (VN30 + Midcap + Small) |
| **HNX** | 296 | All stocks on Hanoi Stock Exchange |
| **UPCOM** | 300 | Top 300 representative symbols (from 743 total) |
| **Index** | 9 | VNINDEX, VN30, HNX, HNX30, UPCOM, VN100, VNMID, VNSML, VNALL |
| **Derivatives** | 4 | VN30F Q2-Q3 2026 (VN30F2604/05/06/09) |
| **Total** | **1012** | |

### Data Retention & Aggregation

| Timeframe | Retention | Iceberg Table | Notes |
|-----------|-----------|---------------|-------|
| **1m** | 90 days | `iceberg.bronze.vnstock_ohlc_1m` | Raw + streaming appends |
| **5m** | 90 days | `iceberg.bronze.vnstock_ohlc_5m` | Aggregated from 1m |
| **15m** | 90 days | `iceberg.bronze.vnstock_ohlc_15m` | Aggregated from 1m |
| **30m** | 90 days | `iceberg.bronze.vnstock_ohlc_30m` | Aggregated from 1m |
| **1h** | 90 days | `iceberg.bronze.vnstock_ohlc_1h` | Aggregated from 1m |
| **4h** | 90 days | `iceberg.bronze.vnstock_ohlc_4h` | Aggregated from 1m |
| **1D** | From 2015 | `iceberg.gold.vnstock_ohlc_1d` | Daily OHLCV |

---

## PySpark Jobs

Both the **realtime** and **batch** pipelines use PySpark:

| Job | File | Type | Description |
|-----|------|------|-------------|
| **Realtime Streaming** | `streaming.py` | Structured Streaming | Kafka JSON → Iceberg append + Redis update (10s trigger) |
| **Backfill 1m** | `backfill_1m.py` | Batch | DNSE REST → 1m + auto-aggregate 5m/15m/30m/1h/4h |
| **Backfill 1D** | `backfill_1d.py` | Batch | DNSE REST resolution=1D → Gold daily (from 2015) |
| **Compact** | `compact.py` | Batch | Bronze → Silver (dedup + repartition by symbol) |
| **News Crawler** | `news_crawler.py` | Batch | CafeF/Vietstock/VnEconomy → Redis |

---

## Quick Start

### Prerequisites

| Requirement | Details |
|-------------|---------|
| **Docker Desktop** | Latest version (or Docker Engine 24+ with Compose v2) |
| **RAM** | Minimum **16GB** (recommended **32GB** for full stack) |
| **Disk** | Minimum **50GB** free (Iceberg data + Docker images) |
| **OS** | Windows 10/11 (WSL2), macOS, or Linux |
| **DNSE API Key** | Register at [dnse.com.vn](https://dnse.com.vn) (free) |

### Step 1: Clone & Configure

```bash
git clone <repo-url>
cd lakehouse-oss-vuong.ngo

cp .env.example .env
# Edit .env:
#   DNSE_API_KEY=<your-api-key>
#   VNSTOCK_SYMBOLS is pre-configured with 1012 symbols
```

### Step 2: Start the VVS Stack

```bash
# Start all 13 services: Kafka, Spark, MinIO, Redis, Trino, Producer, API, Frontend
docker compose --profile vnstock up -d

# Verify all services are running:
docker compose --profile vnstock ps

# Wait ~60s for Kafka + Hive Metastore to initialize
```

### Step 3: Verify the Pipeline

```bash
# Check Producer is fetching data from DNSE:
docker logs lakehouse-oss-vuongngo-vnstock-producer-1 --tail 10
# Expected: "Cycle #N: 736/1012 symbols → Redis + Kafka (7.3s)"

# Check API is healthy:
curl http://localhost:8060/api/health
# Expected: {"status":"ok","checks":{"redis":"ok","trino":"ok"}}

# Open the frontend dashboard:
# Browser → http://localhost:3080
```

### Step 4: Run Historical Backfill

```bash
# Inside the spark-master container:
docker exec -it lakehouse-oss-vuongngo-spark-master-1 bash

# Backfill 1-minute data (90 days):
/opt/bitnami/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  /opt/spark/jobs/vnstock/backfill_1m.py \
  --days 90

# Backfill daily data (from 2015):
/opt/bitnami/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  /opt/spark/jobs/vnstock/backfill_1d.py
```

### Step 5: Start the Streaming Job

```bash
# Submit the PySpark Structured Streaming job:
docker exec -d lakehouse-oss-vuongngo-spark-master-1 \
  /opt/bitnami/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  /opt/spark/jobs/vnstock/streaming.py
```

### Step 6: Verify Data

```bash
# Check row counts via Trino:
docker exec lakehouse-oss-vuongngo-trino-1 trino --execute \
  "SELECT count(*) FROM iceberg.bronze.vnstock_ohlc_1m"

docker exec lakehouse-oss-vuongngo-trino-1 trino --execute \
  "SELECT count(*) FROM iceberg.gold.vnstock_ohlc_1d"
```

---

## Service Endpoints

| Service | URL | Credentials | Description |
|---------|-----|-------------|-------------|
| **VVS Dashboard** | http://localhost:3080 | — | TradingView-style chart + watchlist |
| **FastAPI Docs** | http://localhost:8060/api/docs | — | Swagger UI |
| **Spark Master** | http://localhost:8088 | — | Cluster status + running apps |
| **Trino** | http://localhost:8090 | — | SQL engine UI |
| **MinIO Console** | http://localhost:9001 | minio / minio123 | Object storage UI |
| Airflow | http://localhost:8080 | airflow / airflow | DAG management |
| Kafka | localhost:9092 | — | External broker access |
| Redis | localhost:6379 | — | Internal cache |

---

## API Reference

| Method | Endpoint | Params | Source | Description |
|--------|----------|--------|--------|-------------|
| `GET` | `/api/history` | `symbol`, `interval`, `limit`, `end_time` | Iceberg via Trino | Historical candles (7 timeframes) |
| `GET` | `/api/realtime` | `symbol` (optional) | Redis | Current real-time tick (single or all) |
| `GET` | `/api/realtime/quote` | `symbol` | Redis | Bid/Ask depth (10 levels) |
| `GET` | `/api/realtime/secdef` | `symbol` | Redis | Security definition (ceiling/floor/reference) |
| `GET` | `/api/realtime/summary` | `symbol` | Redis (pipeline) | Combined tick + quote + secdef |
| `GET` | `/api/news` | `source`, `limit` | Redis sorted set | Market news |
| `GET` | `/api/symbols` | — | Config | Symbol list |
| `WS` | `/api/ws/stream` | `symbol` | Redis (poll 1s) | Bidirectional real-time streaming |
| `GET` | `/api/health` | — | Redis + Trino | Health check |

### WebSocket Protocol

```
Server → Client:
  {"type": "tick",  "data": {symbol, time, open, high, low, close, volume}}
  {"type": "quote", "data": {symbol, bid[], offer[], ...}}
  {"type": "ping"}

Client → Server:
  {"type": "subscribe", "symbol": "HPG"}   // switch symbol without reconnect
  {"type": "pong"}                          // heartbeat reply
```

---

## Project Structure

```
lakehouse-oss-vuong.ngo/
├── docker-compose.yml                # All services, profile-based deployment
├── .env                              # Environment variables (DNSE_API_KEY, symbols)
│
├── infra/
│   ├── vnstock/                      # ═══ DNSE REST Producer ═══
│   │   ├── Dockerfile
│   │   ├── producer.py               # DNSE REST → Kafka (JSON, lz4) + Redis
│   │   └── requirements.txt          # requests, redis, kafka-python, lz4
│   │
│   ├── vnstock-api/                  # ═══ FastAPI Backend ═══
│   │   └── app/
│   │       ├── main.py               # Startup, GZip, CORS
│   │       ├── connections.py        # Redis async pool + Trino sync factory
│   │       └── routers/
│   │           ├── history.py        # GET /api/history (Iceberg via Trino)
│   │           ├── realtime.py       # GET /api/realtime (Redis)
│   │           ├── ws.py             # WS /api/ws/stream (bidirectional)
│   │           ├── news.py           # GET /api/news
│   │           └── symbols.py        # GET /api/symbols
│   │
│   ├── vnstock-frontend/             # ═══ React Frontend ═══
│   │   └── src/
│   │       ├── App.js                # 3-column layout
│   │       ├── components/
│   │       │   ├── CandlestickChart.js  # TradingView-style, SMA/EMA
│   │       │   ├── QuotePanel.js        # Bid/Ask depth
│   │       │   ├── Watchlist.js         # Symbol list + real-time prices
│   │       │   └── NewsTicker.js        # Market news
│   │       └── services/
│   │           └── api.js            # API layer + WS client
│   │
│   ├── airflow/                      # ═══ Orchestration ═══
│   │   ├── dags/
│   │   │   ├── vnstock_bronze_dag.py    # Bronze Kafka ingest scheduling
│   │   │   └── vnstock_backfill_news_dag.py # Backfill + news crawl DAGs
│   │   └── processing/spark/jobs/vnstock/
│   │       ├── streaming.py          # Kafka JSON → Iceberg + Redis (PySpark Streaming)
│   │       ├── backfill_1m.py        # DNSE REST → 1m + aggregate (PySpark Batch)
│   │       ├── backfill_1d.py        # DNSE REST → daily from 2015 (PySpark Batch)
│   │       ├── compact.py            # Bronze → Silver dedup
│   │       └── news_crawler.py       # CafeF/Vietstock → Redis
│   │
│   └── spark/                        # ═══ Spark Cluster ═══
│       └── Dockerfile                # Bitnami Spark 3.5.6 + pyarrow, redis, vnstock
│
├── config/
│   └── spark-defaults.conf           # Iceberg catalog + MinIO + Spark tuning
│
└── README_VNSTOCK.md                 # This file
```

---

## Performance Metrics

| Metric | Value | How to verify |
|--------|-------|---------------|
| **Producer cycle** | 736/1012 symbols in ~7s | `docker logs vnstock-producer --tail 5` |
| **Kafka topic** | `vnstock.ohlc.realtime` (JSON, lz4) | `docker exec kafka kafka-topics.sh --list` |
| **Streaming throughput** | ~2000+ rows/30s append to Iceberg | Trino: `SELECT count(*) FROM iceberg.bronze.vnstock_ohlc_1m` |
| **1m data volume** | 2.6M+ rows (961 symbols, 90 days) | Trino query |
| **1d data volume** | 2.1M+ rows (999 symbols, from 2015) | Trino query |
| **API response** | < 200ms (history), < 50ms (realtime) | FastAPI Swagger |
| **WS update rate** | 1 tick/second per symbol | Browser DevTools → WS tab |
| **Frontend chart** | 7 timeframes, SMA 20 + EMA 50 | http://localhost:3080 |

---

## Docker Compose Profiles

| Profile | Command | Services | Description |
|---------|---------|----------|-------------|
| **vnstock** | `docker compose --profile vnstock up -d` | 13 | Full VVS stack |
| **monitoring** | `docker compose --profile monitoring up -d` | 8 | Prometheus + Grafana + Loki |
| **airflow** | `docker compose --profile airflow up -d` | 6 | Airflow scheduler + workers |

### Resource Configuration

| Service | Memory Limit | CPU Limit | Notes |
|---------|-------------|-----------|-------|
| spark-master | 2GB | 2 cores | Driver + job coordination |
| spark-worker-1 | 4GB | 2 cores | Primary executor |
| spark-worker-2 | 4GB | 2 cores | Secondary executor |
| kafka | 1.5GB | 1 core | KRaft mode (no ZooKeeper) |
| trino | 1.5GB | 1 core | Query engine |
| minio | 512MB | 0.5 core | Object storage |
| redis | 256MB | 0.25 core | Tick cache |
| vnstock-producer | 512MB | 0.5 core | REST poller |
| vnstock-api | 512MB | 0.5 core | FastAPI backend |
| vnstock-frontend | 256MB | 0.25 core | React dev server |
| hive-metastore | 1.5GB | 1 core | Iceberg catalog |
| postgres-hive | 256MB | 0.25 core | Metastore backend |

---

## Key Design Decisions

1. **DNSE REST over WebSocket**: DNSE's WebSocket endpoints use gRPC-web protocol (not standard WebSocket), making them inaccessible from server-side Python. The REST API with an API key has no rate limit and achieves ~25 req/s with connection pooling.

2. **Kafka as the central bus**: Producer writes to both Kafka (for persistence via PySpark Streaming) and Redis (for low-latency frontend serving). This decouples ingestion from processing.

3. **PySpark for both pipelines**: Both the real-time streaming (Kafka → Iceberg + Redis) and batch backfill (DNSE REST → Iceberg) use PySpark, ensuring a consistent processing framework across the Lambda Architecture.

4. **Iceberg on MinIO**: ACID transactions, time-travel queries, and schema evolution on S3-compatible storage. Zero vendor lock-in.

5. **FastAPI WebSocket to frontend**: The internal WebSocket between FastAPI and the React frontend polls Redis every second. This provides a true WebSocket experience to the browser while the backend uses REST for data ingestion.

6. **JSON over Avro for Kafka**: The producer publishes JSON to Kafka (not Avro) for simplicity and debuggability. PySpark's `from_json()` parsing is sufficient for the data volume (~1000 messages every 15 seconds).

---

## Troubleshooting

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| Producer: 0/1012 symbols | DNSE API key missing or expired | Check `.env` DNSE_API_KEY, test with `curl` |
| Kafka: no messages | Producer not connected to Kafka | Check `docker logs kafka`, verify `kafka:29092` reachable |
| Streaming: no new rows | Spark job not running | `docker exec spark-master ls /opt/bitnami/spark/work/` |
| Frontend: no chart | API down or CORS issue | Check `http://localhost:8060/api/health` |
| Trino: query timeout | Iceberg metadata issue | Restart hive-metastore, then trino |
| High memory usage | Spark executors | Reduce `spark.executor.memory` in `spark-defaults.conf` |

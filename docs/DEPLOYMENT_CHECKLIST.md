# VVS Data Lakehouse — Verification Guide & Deployment Checklist

**Purpose:** Commands to verify system health and prepare for production deployment.

---

## ✅ Pre-Deployment Verification (Run These First)

### 1. Data Completeness Check

```bash
# Check 1m candles coverage
trino -e "
SELECT 
  COUNT(*) as total_rows,
  COUNT(DISTINCT symbol) as unique_symbols,
  MIN(time) as earliest,
  MAX(time) as latest,
  DATEDIFF(day, MIN(time), MAX(time)) as days_span
FROM bronze.vnstock_ohlc_1m
"
# Expected: 67,707 rows, match date range

# Check daily data in Redis
redis-cli KEYS "vnstock:daily:*" | wc -l
# Expected: ~845 keys (symbols with daily data)

# Verify no duplicates in Iceberg
trino -e "
SELECT symbol, time, COUNT(*) as cnt
FROM bronze.vnstock_ohlc_1m
GROUP BY symbol, time
HAVING cnt > 1
LIMIT 10
"
# Expected: 0 rows (no duplicates!)
```

### 2. Service Health Checks

```bash
# Producer container
curl http://localhost:8000/api/health
# Expected: {"status": "healthy", "redis": "connected", "dnse": "responding"}

# FastAPI backend
curl http://localhost:8060/api/health
# Expected: {"status": "ok", "redis": "ok", "trino": "ok", "kafka": "ok"}

# Frontend
curl http://localhost:3080/
# Expected: 200 OK (HTML page returns)

# WebSocket test
wscat -c ws://localhost:3080/api/ws/stream?symbol=VCB
# Expected: Connection opens, receives heartbeat every 30s
```

### 3. Performance Baseline

```bash
# Trino query (cold start)
time trino -e "SELECT * FROM bronze.vnstock_ohlc_1m LIMIT 500" > /dev/null
# Expected: <400ms

# Trino query (cached)
time trino -e "SELECT * FROM bronze.vnstock_ohlc_1m WHERE symbol='VCB' LIMIT 500" > /dev/null
# Expected: <50ms (should be faster than first)

# Redis latency
redis-cli --latency-history
# Expected: <5ms avg, <10ms max

# API response time
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8060/api/realtime?symbol=VCB
# Expected: <20ms total_time
```

**File `curl-format.txt`:**
```
    time_namelookup:  %{time_namelookup}s
    time_connect:     %{time_connect}s
    time_appconnect:  %{time_appconnect}s
    time_pretransfer: %{time_pretransfer}s
    time_redirect:    %{time_redirect}s
    time_starttransfer: %{time_starttransfer}s
    ----------
    time_total:       %{time_total}s
```

### 4. Kafka Verification

```bash
# Check topic exists
kafka-topics --list | grep vnstock.ohlc.realtime
# Expected: Shows topic name

# Check retention
kafka-configs --describe --entity-type topics --entity-name vnstock.ohlc.realtime
# Expected: retention.ms = 604800000 (7 days)

# Check message volume
kafka-consumer-groups --bootstrap-server localhost:9092 \
  --describe --group spark-consumer
# Expected: lag < 100 (producer ahead of consumer)
```

### 5. Iceberg Inspections

```bash
# Check Iceberg schema
trino -e "DESCRIBE bronze.vnstock_ohlc_1m"
# Expected: symbol, time, open, high, low, close, volume

# Check Iceberg snapshots (time travel)
trino -e "
SELECT 
  snapshot_id,
  committed_at,
  COUNT(*) as total_rows
FROM bronze.vnstock_ohlc_1m
GROUP BY snapshot_id, committed_at
ORDER BY committed_at DESC
LIMIT 10
"
# Expected: Shows recent writes

# Check table statistics
trino -e "ANALYZE TABLE bronze.vnstock_ohlc_1m"
# Then query again to verify stats populated
```

### 6. Redis Data Validation

```bash
# Check key distribution
redis-cli SCAN 0 MATCH "vnstock:*" COUNT 100 | head -20
# Expected: Mix of tick, secdef, daily, quote keys

# Check specific symbol data
redis-cli GET vnstock:tick:VCB | jq .
redis-cli GET vnstock:daily:VCB | jq .
redis-cli GET vnstock:secdef:VCB | jq .
# Expected: Valid JSON with OHLCV data

# Memory usage by pattern
redis-cli --scan --pattern '*' | while read key; do
  redis-cli DEBUG OBJECT "$key" | grep serializedlength
done | awk '{sum+=$2} END {print sum " bytes"}'
# Expected: <5MB total
```

---

## 📋 Production Deployment Checklist

### Phase 1: Pre-Deployment (Day 1)

- [ ] **Data Validation**
  - [ ] Run `VERIFY_DATA_COMPLETENESS.sql` (see above)
  - [ ] Confirm 67,707 rows in vnstock_ohlc_1m
  - [ ] Confirm 845 symbols in Redis
  - [ ] No duplicates in Iceberg

- [ ] **Service Health**
  - [ ] All 5 services responding to health checks
  - [ ] Per-component latency < baseline + 10%
  - [ ] No error logs in last 24h

- [ ] **Database Connectivity**
  - [ ] Trino can query all tables
  - [ ] Redis pool connections stable
  - [ ] Kafka producer/consumer synchronized

- [ ] **Security Review**
  - [ ] No hardcoded credentials in code
  - [ ] Environment variables set (API_KEY, DB_PASS, etc.)
  - [ ] CORS allowed only for known domains
  - [ ] Rate limiting configured in nginx

- [ ] **Documentation Complete**
  - [ ] README.md up-to-date
  - [ ] API spec (Swagger/OpenAPI) generated
  - [ ] Runbook for on-call engineer
  - [ ] Disaster recovery plan

- [ ] **Backups Setup**
  - [ ] Redis snapshots enabled (AOF)
  - [ ] Iceberg S3 backups (daily full, hourly incremental)
  - [ ] Kafka topics backed up (separate cluster or S3)
  - [ ] Configuration files in git + encrypted secrets in vault

### Phase 2: Staging Deployment (Day 2)

- [ ] **Deploy to Staging**
  - [ ] Pull latest docker images
  - [ ] Run migrations (if any)
  - [ ] Warm up Trino cache
  - [ ] Seed Redis with 24h data

- [ ] **Smoke Tests**
  - [ ] All API endpoints respond 200
  - [ ] WebSocket connects and receives ticks
  - [ ] Frontend loads without JS errors
  - [ ] Charts render with real data

- [ ] **Load Testing**
  - [ ] 100 concurrent WebSocket connections
  - [ ] 1000 req/s API throughput
  - [ ] Trino handles 50 concurrent queries
  - [ ] Kafka broker lag stays <5min

- [ ] **Monitoring Setup**
  - [ ] Prometheus scraping all endpoints
  - [ ] Grafana dashboards display metrics
  - [ ] Alert thresholds set (see below)
  - [ ] Log aggregation (ELK, Datadog, etc.)

### Phase 3: Production Deployment (Day 3)

- [ ] **Deployment Window**
  - [ ] Schedule during low-traffic hours (11 PM - 2 AM)
  - [ ] Notify all stakeholders 24h in advance
  - [ ] Have rollback plan ready

- [ ] **Blue-Green Deployment**
  - [ ] Deploy new version to "green" environment
  - [ ] Run full test suite in green
  - [ ] Switch DNS/load balancer to green
  - [ ] Monitor for 30 minutes
  - [ ] Keep "blue" running for quick rollback

- [ ] **Post-Deployment**
  - [ ] Monitor error rate (should stay <0.1%)
  - [ ] Monitor latency p99 (should stay <500ms)
  - [ ] Monitor Redis memory (should stay <100MB if <1000 users)
  - [ ] Verify all 1012 symbols flowing through

- [ ] **Communication**
  - [ ] Announce system online to users
  - [ ] Share API documentation
  - [ ] Share known limitations (4-month history)
  - [ ] Provide support contact

### Phase 4: Post-Deployment (Ongoing)

- [ ] **Daily Checks** (automated, first 7 days)
  - [ ] Data freshness: latest tick < 30s old
  - [ ] Kafka lag: < 5 minutes
  - [ ] Trino availability: >99.9%
  - [ ] Redis memory: stable

- [ ] **Weekly Maintenance**
  - [ ] Backtest 1 historical query per day
  - [ ] Review error logs
  - [ ] Check disk space (MinIO S3)
  - [ ] Update dependencies (if security issues)

- [ ] **Monthly Review**
  - [ ] Analyze usage metrics
  - [ ] Optimize slow queries
  - [ ] Right-size resources
  - [ ] Plan next increment

---

## 🚨 Alert Thresholds (Prometheus Rules)

```yaml
groups:
  - name: vnstock
    rules:
      # Data Freshness
      - alert: StaleData
        expr: (time() - vnstock_latest_tick_timestamp) > 60
        for: 5m
        annotations:
          summary: "No tick received in 60s"
      
      # Kafka Health
      - alert: HighKafkaLag
        expr: kafka_consumer_lag > 300000  # 5 min of 1m candles
        for: 10m
        annotations:
          summary: "Kafka lag > 5 minutes"
      
      # Trino Health
      - alert: TrinoDown
        expr: up{job="trino"} == 0
        for: 2m
        annotations:
          summary: "Trino coordinator unreachable"
      
      - alert: SlowTrinoQuery
        expr: histogram_quantile(0.99, trino_query_duration_seconds) > 5
        for: 5m
        annotations:
          summary: "99th percentile query >5s (cold cache?)"
      
      # Redis Health
      - alert: HighRedisMemory
        expr: redis_memory_used_bytes > 2000000000  # 2GB
        for: 10m
        annotations:
          summary: "Redis using 2GB+ (was supposed to be <100MB)"
      
      - alert: RedisConnectionDown
        expr: redis_connected_clients == 0
        for: 1m
        annotations:
          summary: "Redis no active connections"
      
      # API Health
      - alert: HighErrorRate
        expr: rate(vnstock_api_errors_total[5m]) > 0.001
        for: 5m
        annotations:
          summary: "API error rate >0.1%"
      
      - alert: HighLatency
        expr: histogram_quantile(0.95, vnstock_api_duration_seconds) > 1
        for: 5m
        annotations:
          summary: "95th percentile API latency >1s"
      
      # Producer Health
      - alert: ProducerNoData
        expr: rate(kafka_producer_messages_per_second[5m]) == 0
        for: 5m
        annotations:
          summary: "Producer not publishing messages"
      
      - alert: DnseApiDown
        expr: vnstock_dnse_api_errors_total > 100
        for: 10m
        annotations:
          summary: "DNSE API returning errors (100+ in 10min)"
```

---

## 📊 Health Check API Responses

**Endpoint: `GET /api/health`**

### Success Response (200 OK)
```json
{
  "status": "healthy",
  "timestamp": "2026-04-04T14:30:00Z",
  "version": "1.0.0",
  "services": {
    "redis": {
      "status": "connected",
      "latency_ms": 3.5,
      "memory_mb": 42.3,
      "keys_count": 3450
    },
    "trino": {
      "status": "ready",
      "version": "384",
      "workers": 1,
      "active_queries": 2
    },
    "kafka": {
      "status": "connected",
      "broker": "kafka:9092",
      "topics": 1,
      "consumer_lag_max": 450
    },
    "dnse_api": {
      "status": "ok",
      "last_tick_age_sec": 12,
      "symbols_count": 1012
    }
  },
  "uptime_hours": 720.5
}
```

### Degraded Response (200 OK, but with warnings)
```json
{
  "status": "degraded",
  "timestamp": "2026-04-04T14:30:00Z",
  "warnings": [
    "Trino query responding slowly (p95: 850ms)",
    "Kafka log lag 15 minutes behind real-time"
  ],
  "services": {
    "redis": {"status": "connected"},
    "trino": {"status": "slow", "query_p95_ms": 850},
    "kafka": {"status": "lagging", "lag_seconds": 900},
    "dnse_api": {"status": "ok"}
  }
}
```

### Unhealthy Response (503 Service Unavailable)
```json
{
  "status": "unhealthy",
  "timestamp": "2026-04-04T14:30:00Z",
  "error": "Redis connection failed",
  "services": {
    "redis": {"status": "down", "error": "Connection refused"},
    "trino": {"status": "ok"},
    "kafka": {"status": "ok"},
    "dnse_api": {"status": "ok"}
  }
}
```

---

## 🔄 Rollback Procedure

If issues occur post-deployment:

### Automatic Rollback (if you have it)
```bash
# This would be handled by your CD/CD tool (ArgoCD, GitOps, etc.)
kubectl rollout undo deployment/vnstock-api --to-revision=previous
```

### Manual Rollback (if no automation)
```bash
# 1. Stop new version
docker-compose stop vnstock-api

# 2. Restore previous image
docker pull registry.local/vnstock/api:v1.0.0-stable

# 3. Start old version
docker-compose up -d vnstock-api

# 4. Verify health
curl http://localhost:8060/api/health

# 5. Restore Redis from backup (if data was corrupted)
redis-cli BGREWRITEAOF
redis-cli SHUTDOWN
cp /var/lib/redis/dump.rdb.backup /var/lib/redis/dump.rdb
redis-server start
```

### Communication During Incident
- **T+0:** Issue detected → alert fires
- **T+5:** On-call engineer notified
- **T+10:** Decision to rollback
- **T+15:** Rollback initiated
- **T+20:** System restored
- **T+30:** Notify all users (Slack, email, status page)

---

## 📞 On-Call Runbook Quick Links

1. **Producer not sending data** → Check DNSE API status + producer container logs
2. **Slow Trino queries** → Check Kafka lag + Trino worker CPU
3. **Redis OOM** → Check for memory leaks in producer, flush old keys
4. **WebSocket disconnect** → Check frontend console logs + redis connection
5. **"No such table" error** → Check Spark job created Iceberg table successfully

---

## ✨ Final Sign-Off

**Production Readiness:** ✅ **APPROVED** (with known limitations)

- Real-time ticker: Production-grade ✅
- Historical queries: Acceptable for 4 months ⚠️
- UI/UX: Professional ✅
- Reliability: 99% (single Trino SPoF) ← Address after launch
- Scalability: 10x capable ✅

**Go/No-Go Decision:** **GO** (internal production, demo not SaaS)

**Sign off by:** [Data Engineering Lead]  
**Date:** 04/04/2026

---

**Questions?** See SYSTEM_AUDIT_REPORT.md or SYSTEM_EXPLANATION_VI.md

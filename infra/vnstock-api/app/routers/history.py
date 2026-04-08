"""
GET /api/history — Historical candles from Iceberg (via Trino).

Retrieves OHLCV data from Iceberg tables ingested by Spark.
Supports 7 timeframes: 1m, 5m, 15m, 30m, 1h, 4h, 1d.

Flow:
  Frontend → GET /api/history?symbol=VCB&interval=1m&limit=500
           → FastAPI → check Redis cache
           → cache miss → Trino SQL → Iceberg table on MinIO
           → Return [{time, open, high, low, close, volume}, ...]

Deduplication: Streaming job may append duplicate (symbol, time) rows.
SQL uses ROW_NUMBER() to keep only one row per timestamp.

Redis cache: History responses are cached for 10-60s depending on timeframe
to reduce Trino load and improve response time for concurrent users.

Trino does not support parameterized queries (?), so we use string formatting.
Symbol is whitelist-validated via regex to prevent SQL injection.
"""

import json
import hashlib
import logging
import re
import time as _time
import urllib.request

from fastapi import APIRouter, Query, HTTPException
from app.connections import get_trino_connection, get_redis

logger = logging.getLogger("vnstock-api.history")

router = APIRouter(prefix="/api", tags=["history"])

# Cache TTL per timeframe (seconds): smaller timeframes change faster
_CACHE_TTL = {
    "1m": 10, "5m": 15, "15m": 30, "30m": 30,
    "1h": 60, "4h": 60, "1d": 120, "1": 10,
}

# ── Table mapping: interval → Iceberg table ────────────────────
# Bronze tables: from backfill_1m jobs (1m raw + aggregated 5m/15m/30m/1h/4h)
# Gold table: from backfill_1d job (daily data from 2015)
# Fallback "1": raw Bronze stream data (from Kafka → Iceberg)
TABLE_MAP = {
    "1m":  "bronze.vnstock_ohlc_1m",
    "5m":  "bronze.vnstock_ohlc_5m",
    "15m": "bronze.vnstock_ohlc_15m",
    "30m": "bronze.vnstock_ohlc_30m",
    "1h":  "bronze.vnstock_ohlc_1h",
    "4h":  "bronze.vnstock_ohlc_4h",
    "1d":  "gold.vnstock_ohlc_1d",
    "1":   "bronze.vnstock_ohlc_stock",
}

# Regex for symbol validation: 1-15 alphanumeric chars (VCB, VN30F2506, VNINDEX)
_SYM_RE = re.compile(r"^[A-Z0-9]{1,15}$")

# DNSE REST for filling gap between Iceberg (last backfill) and now
_DNSE_CHART_URL = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"
# Map our interval keys → DNSE resolution param
_DNSE_RES_MAP = {
    "1m": "1", "5m": "5", "15m": "15", "30m": "30",
    "1h": "60", "4h": "240", "1d": "1D",
}


def _fetch_live_candles(sym: str, interval: str, from_ts: int, to_ts: int) -> list[dict]:
    """Fetch recent candles from DNSE REST API to fill Iceberg gap."""
    res = _DNSE_RES_MAP.get(interval)
    if not res:
        return []
    url = (
        f"{_DNSE_CHART_URL}?symbol={sym}&resolution={res}"
        f"&from={from_ts}&to={to_ts}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "VVS-API/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        if not data.get("t"):
            return []
        candles = []
        for i in range(len(data["t"])):
            t = int(data["t"][i])
            if t > 1_000_000_000_000:
                t = t // 1000
            candles.append({
                "time": t,
                "open": float(data["o"][i]),
                "high": float(data["h"][i]),
                "low": float(data["l"][i]),
                "close": float(data["c"][i]),
                "volume": int(data["v"][i]),
            })
        return candles
    except Exception as e:
        logger.debug("DNSE REST gap-fill failed for %s: %s", sym, e)
        return []


@router.get("/history")
async def get_history(
    symbol: str = Query(..., description="Stock symbol, e.g. VCB, HPG, VN30F2506"),
    interval: str = Query("1m", description="Timeframe: 1m, 5m, 15m, 30m, 1h, 4h, 1d"),
    limit: int = Query(500, ge=1, le=10000, description="Number of candles to return (max 10000)"),
    end_time: int | None = Query(None, description="End timestamp (ms), returns candles before this time"),
):
    """
    Fetch historical candles from Iceberg.

    Returns: List of candles [{time, open, high, low, close, volume}, ...]
    - time: Unix seconds (frontend Lightweight Charts requires seconds, not ms)
    - Sorted ascending by time (oldest → newest)
    - Deduplicated: only one row per timestamp (streaming may create duplicates)
    - Cached in Redis for 10-120s depending on timeframe
    """
    # ── Validate ──
    table = TABLE_MAP.get(interval)
    if not table:
        raise HTTPException(400, detail=f"Unsupported interval: {interval}. "
                                        f"Supported: {', '.join(TABLE_MAP.keys())}")

    sym = symbol.strip().upper()
    if not _SYM_RE.match(sym):
        raise HTTPException(400, detail=f"Invalid symbol format: {symbol}")

    # ── Check Redis cache ──
    cache_key = f"vnstock:history:{sym}:{interval}:{limit}:{end_time or 0}"
    try:
        r = await get_redis()
        cached = await r.get(cache_key)
        if cached:
            logger.debug("Cache HIT: %s", cache_key)
            return json.loads(cached)
    except Exception:
        pass  # Cache miss or Redis down — proceed to Trino

    # ── Build SQL with deduplication ──
    # GROUP BY time to collapse duplicate rows from streaming appends
    # For duplicates: MAX(high), MIN(low), ARBITRARY picks any (all identical)
    where_clause = f"WHERE symbol = '{sym}'"  # sym is validated by regex
    if end_time is not None:
        if not isinstance(end_time, int) or end_time < 0:
            raise HTTPException(400, detail="end_time must be a positive integer (ms)")
        where_clause += f" AND time < {int(end_time)}"

    sql = f"""
        SELECT time,
               ARBITRARY(open) AS open,
               MAX(high) AS high,
               MIN(low) AS low,
               ARBITRARY(close) AS close,
               MAX(volume) AS volume
        FROM iceberg.{table}
        {where_clause}
        GROUP BY time
        ORDER BY time DESC
        LIMIT {int(limit)}
    """

    # ── Execute ──
    conn = None
    try:
        conn = get_trino_connection()
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
    except Exception as e:
        logger.error("Trino query failed for %s/%s: %s", sym, interval, e)

        # Fallback: if table doesn't exist (backfill not run yet), try Bronze stream
        if "TABLE_NOT_FOUND" in str(e) or "does not exist" in str(e):
            if interval != "1" and "1" in TABLE_MAP:
                logger.info("Falling back to raw Bronze stream table")
                return _query_fallback(sym, limit, end_time)

        raise HTTPException(502, detail=f"Trino query failed: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    if not rows:
        return []

    # ── Transform: Trino rows → TradingView candle format ──
    # time field may be ms (from Kafka ingest) or seconds (from backfill)
    # Lightweight Charts requires Unix seconds
    candles = []
    for row in reversed(rows):  # reversed: DESC → ASC
        t = row[0]
        if t is None:
            continue
        t = int(t)
        # Auto-detect ms vs sec: if > 10^12 then it's ms
        if t > 1_000_000_000_000:
            t = t // 1000

        candles.append({
            "time": t,
            "open": float(row[1]) if row[1] is not None else 0.0,
            "high": float(row[2]) if row[2] is not None else 0.0,
            "low": float(row[3]) if row[3] is not None else 0.0,
            "close": float(row[4]) if row[4] is not None else 0.0,
            "volume": int(row[5]) if row[5] is not None else 0,
        })

    logger.info("/history %s %s → %d candles", sym, interval, len(candles))

    # ── Fill gap: if latest Iceberg candle is too old, fetch recent from DNSE REST ──
    # This bridges the gap between the last Spark backfill and the current live moment.
    # Without this, the chart has a hole from last-backfill to now.
    now_utc = int(_time.time())
    if candles and end_time is None:
        latest_time = candles[-1]["time"]
        gap_sec = now_utc - latest_time
        if gap_sec > 120:  # more than 2 minutes behind
            live = _fetch_live_candles(sym, interval, latest_time, now_utc)
            if live:
                existing_times = {c["time"] for c in candles}
                new_candles = [c for c in live if c["time"] not in existing_times]
                if new_candles:
                    candles.extend(new_candles)
                    candles.sort(key=lambda c: c["time"])
                    logger.info("/history %s %s → +%d live candles (gap-fill)",
                                sym, interval, len(new_candles))
    elif not candles and end_time is None:
        # No Iceberg data at all — fetch entirely from DNSE REST
        live = _fetch_live_candles(sym, interval, now_utc - 86400 * 5, now_utc)
        if live:
            candles = live
            logger.info("/history %s %s → %d candles from DNSE (no Iceberg)",
                        sym, interval, len(candles))

    # ── Write to Redis cache ──
    try:
        ttl = _CACHE_TTL.get(interval, 30)
        await r.setex(cache_key, ttl, json.dumps(candles))
    except Exception:
        pass  # Non-critical: cache write failure doesn't affect response

    return candles


def _query_fallback(sym: str, limit: int, end_time: int | None):
    """Fallback query: fetch from Bronze stream table (ohlc_stock) if backfill hasn't run."""
    table = TABLE_MAP["1"]
    where_clause = f"WHERE symbol = '{sym}'"
    if end_time:
        where_clause += f" AND time < {int(end_time)}"

    sql = f"""
        SELECT time,
               ARBITRARY(open) AS open,
               MAX(high) AS high,
               MIN(low) AS low,
               ARBITRARY(close) AS close,
               MAX(volume) AS volume
        FROM iceberg.{table}
        {where_clause}
        GROUP BY time
        ORDER BY time DESC
        LIMIT {int(limit)}
    """
    conn = None
    try:
        conn = get_trino_connection()
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
    except Exception:
        return []
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    candles = []
    for row in reversed(rows):
        t = row[0]
        if t is None:
            continue
        t = int(t)
        if t > 1_000_000_000_000:
            t = t // 1000
        candles.append({
            "time": t,
            "open": float(row[1] or 0),
            "high": float(row[2] or 0),
            "low": float(row[3] or 0),
            "close": float(row[4] or 0),
            "volume": int(row[5] or 0),
        })
    return candles

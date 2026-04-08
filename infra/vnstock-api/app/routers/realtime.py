"""
GET /api/realtime — Real-time data from Redis (fallback to Trino/Iceberg).

Primary: reads from Redis (data written by Spark streaming job).
Fallback: if Redis is empty (producer offline), returns latest price from Iceberg 1m table.

Redis key structure:
  vnstock:tick:{SYMBOL}      → JSON: {symbol, time, open, high, low, close, volume, resolution}
  vnstock:quote:{SYMBOL}     → JSON: {symbol, bid[], offer[], totalBidQtty, totalOfferQtty}
  vnstock:secdef:{SYMBOL}    → JSON: {symbol, basicPrice, ceilingPrice, floorPrice, securityStatus}
  vnstock:expected:{SYMBOL}  → JSON: {symbol, expectedTradePrice, expectedTradeQuantity}
  vnstock:ticks:all          → Sorted Set (member=symbol, score=last_update_timestamp)

Endpoints:
  GET /api/realtime            → single symbol or all ticks
  GET /api/realtime/quote      → depth-of-market (bid/ask 10 levels)
  GET /api/realtime/secdef     → reference data (ceiling/floor/reference price)
  GET /api/realtime/expected   → ATO/ATC expected price
  GET /api/realtime/summary    → overview: tick + quote + secdef for one symbol
"""

import json
import logging
import re
import time as _time

from fastapi import APIRouter, Query, HTTPException
from app.connections import get_redis, get_trino_connection

logger = logging.getLogger("vnstock-api.realtime")

router = APIRouter(prefix="/api", tags=["realtime"])

_SYM_RE = re.compile(r"^[A-Z0-9]{1,15}$")

# ── Trino fallback cache (avoid querying Trino every 3s) ────────
_trino_cache: dict = {}           # symbol → tick dict
_trino_cache_all: list = []       # all ticks
_trino_cache_ts: float = 0        # timestamp of last cache refresh
TRINO_CACHE_TTL = 60              # refresh every 60 seconds

# ── Secdef fallback cache (compute from Iceberg when Redis missing) ──
_secdef_iceberg_cache: dict = {}  # symbol → secdef dict
_secdef_iceberg_ts: float = 0
SECDEF_ICEBERG_TTL = 300          # refresh every 5 minutes


def _secdef_from_iceberg(sym: str) -> dict | None:
    """Compute basicPrice from Iceberg gold daily table (prev close of last 2 rows).
    Used as fallback when vnstock:secdef:{sym} is missing from Redis (e.g. local
    instance with no running producer or stale data).
    """
    global _secdef_iceberg_cache, _secdef_iceberg_ts
    now = _time.time()
    cached = _secdef_iceberg_cache.get(sym)
    if cached and (now - _secdef_iceberg_ts) < SECDEF_ICEBERG_TTL:
        return cached
    conn = None
    try:
        conn = get_trino_connection()
        cur = conn.cursor()
        cur.execute(
            f"SELECT close FROM iceberg.gold.vnstock_ohlc_1d "
            f"WHERE symbol = '{sym}' ORDER BY time DESC LIMIT 2"
        )
        rows = cur.fetchall()
        if len(rows) < 2:
            return None
        # rows[0] = today (or latest), rows[1] = previous day = reference price
        prev_close = float(rows[1][0])
        if prev_close <= 0:
            return None
        secdef = {
            "symbol": sym,
            "basicPrice": prev_close,
            "ceilingPrice": round(prev_close * 1.07, 2),
            "floorPrice": round(prev_close * 0.93, 2),
            "source": "iceberg",
        }
        _secdef_iceberg_cache[sym] = secdef
        _secdef_iceberg_ts = now
        return secdef
    except Exception as e:
        logger.debug("Iceberg secdef fallback failed for %s: %s", sym, e)
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _trino_latest_tick(sym: str) -> dict | None:
    """Fallback: get the latest 1m candle from Iceberg (cached 60s)."""
    global _trino_cache, _trino_cache_ts
    now = _time.time()
    if sym in _trino_cache and (now - _trino_cache_ts) < TRINO_CACHE_TTL:
        return _trino_cache[sym]
    # Single symbol lookup
    conn = None
    try:
        conn = get_trino_connection()
        cur = conn.cursor()
        cur.execute(
            f"SELECT time, open, high, low, close, volume "
            f"FROM iceberg.bronze.vnstock_ohlc_1m "
            f"WHERE symbol = '{sym}' "
            f"ORDER BY time DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            return None
        t = int(row[0])
        if t > 1_000_000_000_000:
            t = t // 1000
        tick = {
            "symbol": sym, "time": t,
            "open": float(row[1]) if row[1] else 0.0,
            "high": float(row[2]) if row[2] else 0.0,
            "low": float(row[3]) if row[3] else 0.0,
            "close": float(row[4]) if row[4] else 0.0,
            "volume": int(row[5]) if row[5] else 0,
            "source": "iceberg",
        }
        _trino_cache[sym] = tick
        return tick
    except Exception as e:
        logger.debug("Trino fallback failed for %s: %s", sym, e)
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _trino_latest_ticks_batch(syms: list[str]) -> list[dict]:
    """Fallback: get latest price for all symbols from Iceberg (cached 60s)."""
    global _trino_cache_all, _trino_cache_ts, _trino_cache
    now = _time.time()
    if _trino_cache_all and (now - _trino_cache_ts) < TRINO_CACHE_TTL:
        return _trino_cache_all
    conn = None
    try:
        conn = get_trino_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT symbol, time, open, high, low, close, volume "
            "FROM iceberg.bronze.vnstock_ohlc_1m "
            "WHERE (symbol, time) IN ("
            "  SELECT symbol, max(time) FROM iceberg.bronze.vnstock_ohlc_1m "
            "  GROUP BY symbol"
            ")"
        )
        rows = cur.fetchall()
        results = []
        for row in rows:
            t = int(row[1])
            if t > 1_000_000_000_000:
                t = t // 1000
            tick = {
                "symbol": row[0], "time": t,
                "open": float(row[2]) if row[2] else 0.0,
                "high": float(row[3]) if row[3] else 0.0,
                "low": float(row[4]) if row[4] else 0.0,
                "close": float(row[5]) if row[5] else 0.0,
                "volume": int(row[6]) if row[6] else 0,
                "source": "iceberg",
            }
            results.append(tick)
            _trino_cache[row[0]] = tick
        _trino_cache_all = results
        _trino_cache_ts = now
        return results
    except Exception as e:
        logger.debug("Trino batch fallback failed: %s", e)
        return _trino_cache_all  # stale cache is better than empty
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@router.get("/realtime")
async def get_realtime(
    symbol: str | None = Query(None, description="Stock symbol (VCB). Leave empty for all."),
):
    """
    Get current real-time tick.

    - If `symbol` is provided: returns the tick for that single symbol
    - If omitted: returns all symbols currently in Redis (from sorted set)
    """
    r = await get_redis()

    if symbol:
        sym = symbol.strip().upper()
        if not _SYM_RE.match(sym):
            raise HTTPException(400, detail=f"Invalid symbol: {symbol}")
        data = await r.get(f"vnstock:tick:{sym}")
        if data:
            tick = json.loads(data)
            if tick.get("time") and tick["time"] > 1_000_000_000_000:
                tick["time"] = tick["time"] // 1000
            return {"symbol": sym, "data": tick}
        # Fallback: Trino/Iceberg
        tick = _trino_latest_tick(sym)
        return {"symbol": sym, "data": tick}

    # ── All symbols: batch GET qua pipeline ──
    members = await r.zrevrange("vnstock:ticks:all", 0, 1499, withscores=True)
    if members:
        syms = [m for m, _ in members]
        pipe = r.pipeline()
        for sym in syms:
            pipe.get(f"vnstock:tick:{sym}")
        values = await pipe.execute()

        results = []
        for sym, val in zip(syms, values):
            if val:
                tick = json.loads(val)
                if tick.get("time") and tick["time"] > 1_000_000_000_000:
                    tick["time"] = tick["time"] // 1000
                results.append(tick)
        return results

    # Fallback: Trino/Iceberg (Redis empty, producer offline)
    return _trino_latest_ticks_batch([])


@router.get("/realtime/quote")
async def get_quote(
    symbol: str = Query(..., description="Stock symbol"),
):
    """Depth of Market: 10 bid/ask price levels."""
    r = await get_redis()
    data = await r.get(f"vnstock:quote:{symbol.strip().upper()}")
    if not data:
        return None
    return json.loads(data)


@router.get("/realtime/secdef")
async def get_secdef(
    symbol: str = Query(..., description="Stock symbol"),
):
    """Security Definition: reference, ceiling, and floor prices + trading status."""
    r = await get_redis()
    data = await r.get(f"vnstock:secdef:{symbol.strip().upper()}")
    if not data:
        return None
    return json.loads(data)


@router.get("/realtime/expected")
async def get_expected(
    symbol: str = Query(..., description="Stock symbol"),
):
    """Expected Price: projected ATO/ATC price."""
    r = await get_redis()
    data = await r.get(f"vnstock:expected:{symbol.strip().upper()}")
    if not data:
        return None
    return json.loads(data)


@router.get("/realtime/summary")
async def get_summary(
    symbol: str = Query(..., description="Stock symbol"),
):
    """
    Summary: tick + quote + secdef + expected for a single symbol.
    Frontend uses this endpoint when user clicks a Watchlist item.
    """
    r = await get_redis()
    sym = symbol.strip().upper()

    pipe = r.pipeline()
    pipe.get(f"vnstock:tick:{sym}")
    pipe.get(f"vnstock:quote:{sym}")
    pipe.get(f"vnstock:secdef:{sym}")
    pipe.get(f"vnstock:expected:{sym}")
    pipe.get(f"vnstock:daily:{sym}")
    tick_raw, quote_raw, secdef_raw, expected_raw, daily_raw = await pipe.execute()

    result = {"symbol": sym}
    if tick_raw:
        tick = json.loads(tick_raw)
        if tick.get("time") and tick["time"] > 1_000_000_000_000:
            tick["time"] = tick["time"] // 1000
        result["tick"] = tick
    if quote_raw:
        result["quote"] = json.loads(quote_raw)
    if secdef_raw:
        result["secdef"] = json.loads(secdef_raw)
    else:
        # Fallback: compute basicPrice from Iceberg daily table when Redis has no secdef
        # (local instance with no running producer, or first startup before batch layer runs)
        iceberg_secdef = _secdef_from_iceberg(sym)
        if iceberg_secdef:
            result["secdef"] = iceberg_secdef
    if expected_raw:
        result["expected"] = json.loads(expected_raw)
    if daily_raw:
        result["daily"] = json.loads(daily_raw)

    return result


@router.get("/realtime/daily")
async def get_daily(
    symbol: str | None = Query(None, description="Stock symbol. Leave empty for all."),
):
    """
    Daily OHLCV with basicPrice/ceilingPrice/floorPrice merged from secdef.
    Written by producer from DNSE resolution=D candles.
    """
    r = await get_redis()

    if symbol:
        sym = symbol.strip().upper()
        daily_raw, secdef_raw = await r.mget(f"vnstock:daily:{sym}", f"vnstock:secdef:{sym}")
        if not daily_raw:
            return None
        result = json.loads(daily_raw)
        if secdef_raw:
            sd = json.loads(secdef_raw)
            result["basicPrice"] = sd.get("basicPrice")
            result["ceilingPrice"] = sd.get("ceilingPrice")
            result["floorPrice"] = sd.get("floorPrice")
        elif not result.get("basicPrice"):
            # Fallback: compute from Iceberg when secdef not in Redis
            iceberg_secdef = _secdef_from_iceberg(sym)
            if iceberg_secdef:
                result["basicPrice"] = iceberg_secdef["basicPrice"]
                result["ceilingPrice"] = iceberg_secdef["ceilingPrice"]
                result["floorPrice"] = iceberg_secdef["floorPrice"]
        return result

    # All symbols: scan vnstock:daily:* keys
    keys = []
    cursor = 0
    while True:
        cursor, batch = await r.scan(cursor, match="vnstock:daily:*", count=200)
        keys.extend(batch)
        if cursor == 0:
            break
    if not keys:
        return []

    # Derive symbol names from keys (bytes or str)
    syms = [
        (k.decode() if isinstance(k, bytes) else k).split(":")[-1]
        for k in keys
    ]

    # Single pipeline: N daily gets + N secdef gets
    pipe = r.pipeline()
    for k in keys:
        pipe.get(k)
    for sym in syms:
        pipe.get(f"vnstock:secdef:{sym}")
    values = await pipe.execute()

    n = len(keys)
    daily_values = values[:n]
    secdef_values = values[n:]

    results = []
    for daily_val, secdef_val in zip(daily_values, secdef_values):
        if daily_val:
            rec = json.loads(daily_val)
            if secdef_val:
                sd = json.loads(secdef_val)
                rec["basicPrice"] = sd.get("basicPrice")
                rec["ceilingPrice"] = sd.get("ceilingPrice")
                rec["floorPrice"] = sd.get("floorPrice")
            results.append(rec)
    return results

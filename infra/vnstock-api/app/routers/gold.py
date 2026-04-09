"""
GET /api/gold — Pre-computed analytics from the Gold Iceberg layer.

Reads from iceberg.gold.vnstock_daily_summary — built daily by Spark job:
  - change_pct, prev_close, sector mapping
  - Partitioned by trade_date for fast filtering

Endpoints:
  GET /api/gold/daily-summary         → Full daily summary for a given date
  GET /api/gold/daily-summary/latest  → Most recent trading day summary
  GET /api/gold/top-movers            → Top gainers + losers for a given date
  GET /api/gold/sector-summary        → Sector-level aggregation (avg change_pct)
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Query
from app.connections import get_redis, get_trino_connection

logger = logging.getLogger("vnstock-api.gold")

router = APIRouter(tags=["gold"])

GOLD_TABLE = "iceberg.gold.vnstock_daily_summary"
CACHE_TTL = 300  # 5 minutes — gold data refreshes daily


async def _cached_query(cache_key: str, sql: str, ttl: int = CACHE_TTL) -> list[dict]:
    """Execute Trino SQL with Redis caching."""
    r = await get_redis()
    cached = await r.get(cache_key)
    if cached:
        return json.loads(cached)

    try:
        conn = get_trino_connection()
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        if "TABLE_NOT_FOUND" in str(e) or "does not exist" in str(e):
            logger.warning("Gold table not ready: %s", e)
            return []
        raise

    if rows:
        await r.set(cache_key, json.dumps(rows, default=str), ex=ttl)
    return rows


@router.get("/api/gold/daily-summary")
async def daily_summary(
    date: Optional[str] = Query(None, description="Trade date YYYY-MM-DD (default: latest)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
):
    """Full daily summary — change_pct, sector, ref/ceil/floor for all symbols."""
    date_clause = f"trade_date = DATE '{date}'" if date else (
        f"trade_date = (SELECT MAX(trade_date) FROM {GOLD_TABLE})"
    )
    symbol_clause = f"AND symbol = '{symbol.upper()}'" if symbol else ""

    sql = f"""
        SELECT symbol, CAST(trade_date AS VARCHAR) AS trade_date,
               open, high, low, close, volume,
               prev_close, change, change_pct,
               ref_price, ceiling_price, floor_price, sector
        FROM {GOLD_TABLE}
        WHERE {date_clause} {symbol_clause}
        ORDER BY symbol
    """
    cache_key = f"vnstock:gold:daily:{date or 'latest'}:{symbol or 'all'}"
    return await _cached_query(cache_key, sql)


@router.get("/api/gold/daily-summary/latest")
async def daily_summary_latest():
    """Latest trading day summary for all symbols."""
    sql = f"""
        SELECT symbol, CAST(trade_date AS VARCHAR) AS trade_date,
               open, high, low, close, volume,
               prev_close, change, change_pct,
               ref_price, ceiling_price, floor_price, sector
        FROM {GOLD_TABLE}
        WHERE trade_date = (SELECT MAX(trade_date) FROM {GOLD_TABLE})
        ORDER BY symbol
    """
    cache_key = "vnstock:gold:daily:latest:all"
    return await _cached_query(cache_key, sql)


@router.get("/api/gold/top-movers")
async def top_movers(
    date: Optional[str] = Query(None, description="Trade date YYYY-MM-DD"),
    limit: int = Query(10, ge=1, le=50, description="Number of top/bottom results"),
):
    """Top gainers and losers by change_pct."""
    date_clause = f"trade_date = DATE '{date}'" if date else (
        f"trade_date = (SELECT MAX(trade_date) FROM {GOLD_TABLE})"
    )

    sql_top = f"""
        SELECT symbol, CAST(trade_date AS VARCHAR) AS trade_date,
               close, change, change_pct, volume, sector
        FROM {GOLD_TABLE}
        WHERE {date_clause} AND change_pct IS NOT NULL AND volume > 0
        ORDER BY change_pct DESC
        LIMIT {limit}
    """
    sql_bottom = f"""
        SELECT symbol, CAST(trade_date AS VARCHAR) AS trade_date,
               close, change, change_pct, volume, sector
        FROM {GOLD_TABLE}
        WHERE {date_clause} AND change_pct IS NOT NULL AND volume > 0
        ORDER BY change_pct ASC
        LIMIT {limit}
    """

    cache_key = f"vnstock:gold:topmovers:{date or 'latest'}:{limit}"
    r = await get_redis()
    cached = await r.get(cache_key)
    if cached:
        return json.loads(cached)

    conn = get_trino_connection()
    cur = conn.cursor()

    cur.execute(sql_top)
    cols = [desc[0] for desc in cur.description]
    gainers = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(sql_bottom)
    losers = [dict(zip(cols, row)) for row in cur.fetchall()]

    result = {"gainers": gainers, "losers": losers}
    await r.set(cache_key, json.dumps(result, default=str), ex=CACHE_TTL)
    return result


@router.get("/api/gold/sector-summary")
async def sector_summary(
    date: Optional[str] = Query(None, description="Trade date YYYY-MM-DD"),
):
    """Sector-level aggregation: avg change_pct, total volume, stock count."""
    date_clause = f"trade_date = DATE '{date}'" if date else (
        f"trade_date = (SELECT MAX(trade_date) FROM {GOLD_TABLE})"
    )

    sql = f"""
        SELECT sector,
               COUNT(*) AS stock_count,
               ROUND(AVG(change_pct), 2) AS avg_change_pct,
               SUM(volume) AS total_volume,
               SUM(CASE WHEN change_pct > 0 THEN 1 ELSE 0 END) AS gainers,
               SUM(CASE WHEN change_pct < 0 THEN 1 ELSE 0 END) AS losers,
               SUM(CASE WHEN change_pct = 0 THEN 1 ELSE 0 END) AS unchanged
        FROM {GOLD_TABLE}
        WHERE {date_clause} AND sector IS NOT NULL AND volume > 0
        GROUP BY sector
        ORDER BY avg_change_pct DESC
    """
    cache_key = f"vnstock:gold:sector:{date or 'latest'}"
    return await _cached_query(cache_key, sql)

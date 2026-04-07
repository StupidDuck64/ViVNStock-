"""
VNStock API — FastAPI Backend

Serving layer for the VNStock Data Lakehouse.
Provides OHLCV candlestick data for the TradingView-style frontend.

Architecture:
  ┌─────────────┐  /api/history   ┌───────┐   SQL    ┌─────────┐
  │  Frontend   │ ───────────────►│FastAPI │ ────────►│  Trino  │──► Iceberg
  │ (LW Charts) │  /api/realtime  │       │ ────────►│  Redis  │
  │             │◄── WebSocket ───│       │          └─────────┘
  └─────────────┘                 └───────┘

Endpoints:
  GET  /api/history         — Historical candles from Iceberg (via Trino), 7 timeframes
  GET  /api/realtime        — Current tick from Redis (single symbol or all)
  GET  /api/realtime/quote  — Order book bid/ask from Redis
  GET  /api/realtime/secdef — Reference data (ceiling/floor/reference price)
  GET  /api/news            — Market news from Redis
  GET  /api/symbols         — Stock symbol list + classification
  WS   /api/ws/stream       — WebSocket real-time tick (polls Redis every 1s)
  GET  /api/health          — Health check Redis + Trino
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import CORS_ORIGINS
from app.connections import close_all, get_redis, get_trino_connection
from app.routers import history, realtime, news, symbols, ws

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("vnstock-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: warm up Redis pool + verify Trino. Shutdown: close pools."""
    # ── Startup ──
    logger.info("VNStock API starting up...")
    try:
        r = await get_redis()
        await r.ping()
        logger.info("✓ Redis connected: %s", r.connection_pool.connection_kwargs.get("host"))
    except Exception as e:
        logger.warning("✗ Redis not available at startup: %s", e)

    try:
        conn = get_trino_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        logger.info("✓ Trino connected")
    except Exception as e:
        logger.warning("✗ Trino not available at startup: %s", e)

    logger.info("VNStock API ready — endpoints: /api/history, /api/realtime, /api/ws/stream")
    yield

    # ── Shutdown ──
    logger.info("VNStock API shutting down...")
    await close_all()


app = FastAPI(
    title="VNStock Data Lakehouse API",
    version="1.0.0",
    description="Real-time & historical Vietnamese stock market data serving layer",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS — allow frontend to connect (in Docker via nginx, outside Docker needs CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip — compress responses > 500 bytes (historical candle data can be large)
app.add_middleware(GZipMiddleware, minimum_size=500)

# ── Register routers ──
for router in (history.router, realtime.router, news.router, symbols.router, ws.router):
    app.include_router(router)


@app.get("/api/health", tags=["system"])
async def health():
    """Health check — verify Redis and Trino connectivity."""
    checks = {}
    try:
        r = await get_redis()
        pong = await r.ping()
        checks["redis"] = "ok" if pong else "no-pong"
    except Exception as e:
        checks["redis"] = str(e)

    try:
        conn = get_trino_connection()
        cur = conn.cursor()
        cur.execute("SHOW SCHEMAS FROM iceberg")
        schemas = [row[0] for row in cur.fetchall()]
        checks["trino"] = "ok"
        checks["trino_schemas"] = schemas
    except Exception as e:
        checks["trino"] = str(e)

    status = "ok" if all(checks.get(k) == "ok" for k in ["redis", "trino"]) else "degraded"
    return {"status": status, "checks": checks}

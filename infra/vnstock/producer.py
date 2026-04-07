"""
VVS Market Data Producer — Hybrid Architecture (Speed Layer + Batch Layer)

Architecture:
  ┌─────────────────────────────────────────────────────────────────┐
  │  Speed Layer (WebSocket) — tick-by-tick, <100ms latency         │
  │    DNSE WS → trades/ohlc/secdef/quotes → Redis + Kafka          │
  │    Dashboard nhảy tick-by-tick như sàn Binance.                  │
  ├─────────────────────────────────────────────────────────────────┤
  │  Batch Layer (REST) — finalized candles, 60s cadence            │
  │    DNSE REST → finalized 1m candles → Kafka → Iceberg (Bronze)  │
  │    Đảm bảo tính chính xác tuyệt đối cho lịch sử.               │
  └─────────────────────────────────────────────────────────────────┘

Both layers run concurrently in the same container using asyncio.

Speed Layer (WebSocket):
  OHLC 1m updates   → Redis vnstock:tick:{SYM} + Kafka (authoritative live candle)
  Trade ticks        → Redis vnstock:tick:{SYM} + Kafka (builds live 1m candle from individual trades)
  OHLC 1D updates   → Redis vnstock:daily:{SYM}
  SecurityDefinition → Redis vnstock:secdef:{SYM} + vnstock:daily:{SYM}
  Quotes (bid/ask)   → Redis vnstock:quote:{SYM}

Batch Layer (REST, every 60s):
  Finalized 1m candles → Kafka vnstock.ohlc.realtime → Spark → Iceberg (Bronze Layer)
  Daily candles (5min)  → Redis vnstock:daily:{SYM} (secdef fallback)

Redis key structure:
  vnstock:tick:{SYMBOL}   → JSON: latest 1m candle (live, from WS)
  vnstock:ticks:all       → Sorted Set (member=symbol, score=timestamp)
  vnstock:secdef:{SYMBOL} → JSON: {basicPrice, ceilingPrice, floorPrice}
  vnstock:daily:{SYMBOL}  → JSON: {symbol, prevClose, todayClose, changePct, ...}
  vnstock:quote:{SYMBOL}  → JSON: bid/ask depth

Kafka topic:
  vnstock.ohlc.realtime → Confluent Avro wire format
"""

import asyncio
import io
import json
import logging
import os
import signal
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import fastavro
import pytz
import redis.asyncio as aioredis
import requests
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

from trading_websocket import TradingClient
from trading_websocket.models import Trade, Ohlc, SecurityDefinition, Quote

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("vnstock_producer")

# ─── Configuration ───────────────────────────────────────────────
REDIS_HOST       = os.getenv("REDIS_HOST", "redis")
REDIS_PORT       = int(os.getenv("REDIS_PORT", "6379"))
KAFKA_BOOTSTRAP  = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC      = os.getenv("KAFKA_TOPIC", "vnstock.ohlc.realtime")
SCHEMA_REGISTRY  = os.getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")

DNSE_API_KEY     = os.getenv("DNSE_API_KEY", "")
DNSE_API_SECRET  = os.getenv("DNSE_API_SECRET", "")
DNSE_WS_URL      = os.getenv("DNSE_WS_URL", "wss://ws-openapi.dnse.com.vn")
DNSE_CHART_URL   = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"
ENCODING         = os.getenv("WS_ENCODING", "json")

# Symbol lists
SYMBOLS_HOSE_RAW   = os.getenv("VNSTOCK_SYMBOLS_HOSE", "")
SYMBOLS_HNX_RAW    = os.getenv("VNSTOCK_SYMBOLS_HNX", "")
SYMBOLS_UPCOM_RAW  = os.getenv("VNSTOCK_SYMBOLS_UPCOM", "")
SYMBOLS_DERIV_RAW  = os.getenv("VNSTOCK_SYMBOLS_DERIVATIVE", "")
SYMBOLS_INDEX_RAW  = os.getenv("VNSTOCK_SYMBOLS_INDEX", "")
SYMBOLS_ALL_RAW    = os.getenv("SYMBOLS", "")

# Batch layer
REST_INTERVAL     = int(os.getenv("REST_INTERVAL", "60"))
MAX_WORKERS       = int(os.getenv("MAX_WORKERS", "150"))
DAILY_REFRESH     = int(os.getenv("DAILY_REFRESH_INTERVAL", "300"))

# Market hours (Vietnam time UTC+7)
MARKET_HOURS_START = int(os.getenv("MARKET_HOURS_START", "9"))
MARKET_HOURS_END   = int(os.getenv("MARKET_HOURS_END", "15"))
MARKET_TIMEZONE    = os.getenv("MARKET_TIMEZONE", "Asia/Ho_Chi_Minh")

SUB_CHUNK_SIZE = int(os.getenv("SUB_CHUNK_SIZE", "500"))

_session = None  # requests.Session for REST batch layer


def _parse_symbols(raw: str) -> list[str]:
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


def _build_symbol_lists():
    hose  = _parse_symbols(SYMBOLS_HOSE_RAW)
    hnx   = _parse_symbols(SYMBOLS_HNX_RAW)
    upcom = _parse_symbols(SYMBOLS_UPCOM_RAW)
    deriv = _parse_symbols(SYMBOLS_DERIV_RAW)
    index = _parse_symbols(SYMBOLS_INDEX_RAW)
    combined = hose + hnx + upcom + deriv + index
    if not combined:
        combined = _parse_symbols(SYMBOLS_ALL_RAW)
    return {"hose": hose, "hnx": hnx, "upcom": upcom,
            "deriv": deriv, "index": index, "all": combined}


# ─── Avro ────────────────────────────────────────────────────────
OHLC_AVRO_SCHEMA = fastavro.parse_schema({
    "type": "record", "name": "VnstockOhlc", "namespace": "vn.vnstock",
    "fields": [
        {"name": "symbol",     "type": "string"},
        {"name": "time",       "type": "long"},
        {"name": "open",       "type": "double"},
        {"name": "high",       "type": "double"},
        {"name": "low",        "type": "double"},
        {"name": "close",      "type": "double"},
        {"name": "volume",     "type": "long"},
        {"name": "resolution", "type": "string"},
        {"name": "source",     "type": "string"},
    ],
})

_avro_schema_id: int = -1


def _register_avro_schema() -> int:
    subject = f"{KAFKA_TOPIC}-value"
    url = f"{SCHEMA_REGISTRY}/subjects/{subject}/versions"
    payload = {"schema": json.dumps({
        "type": "record", "name": "VnstockOhlc", "namespace": "vn.vnstock",
        "fields": [
            {"name": "symbol", "type": "string"}, {"name": "time", "type": "long"},
            {"name": "open", "type": "double"},   {"name": "high", "type": "double"},
            {"name": "low", "type": "double"},    {"name": "close", "type": "double"},
            {"name": "volume", "type": "long"},   {"name": "resolution", "type": "string"},
            {"name": "source", "type": "string"},
        ],
    })}
    for attempt in range(30):
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            sid = resp.json()["id"]
            logger.info("Avro schema registered: subject=%s, id=%d", subject, sid)
            return sid
        except Exception as e:
            logger.warning("Schema Registry not ready (attempt %d/30): %s", attempt + 1, e)
            time.sleep(2)
    raise RuntimeError("Cannot register Avro schema after 30 attempts")


def _encode_avro(record: dict) -> bytes:
    buf = io.BytesIO()
    buf.write(b'\x00')
    buf.write(struct.pack('>I', _avro_schema_id))
    fastavro.schemaless_writer(buf, OHLC_AVRO_SCHEMA, record)
    return buf.getvalue()


# ─── Market hours ────────────────────────────────────────────────
def is_market_open():
    try:
        tz = pytz.timezone(MARKET_TIMEZONE)
        now = datetime.now(tz)
        if now.weekday() >= 5:
            return False
        return MARKET_HOURS_START <= now.hour < MARKET_HOURS_END
    except Exception:
        return True


# ─── HTTP session (REST batch layer) ─────────────────────────────
def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS,
        )
        _session.mount("https://", adapter)
        if DNSE_API_KEY:
            _session.headers["Authorization"] = f"Bearer {DNSE_API_KEY}"
    return _session


# ─── Stats ───────────────────────────────────────────────────────
_stats = {
    "ws_trades": 0, "ws_ohlc_1m": 0, "ws_ohlc_1d": 0,
    "ws_secdef": 0, "ws_quote": 0,
    "rest_candles": 0, "kafka_sent": 0, "errors": 0,
    "start_time": 0,
}

# ─── Live candle state (build 1m candles from individual trades) ──
_live_candles: dict[str, dict] = {}


# ═════════════════════════════════════════════════════════════════
#   SPEED LAYER — WebSocket (tick-by-tick real-time)
# ═════════════════════════════════════════════════════════════════

async def _write_tick_redis(r: aioredis.Redis, tick: dict):
    """Atomic write: tick data + sorted set membership."""
    sym = tick["symbol"]
    ts = tick["time"]
    pipe = r.pipeline()
    pipe.set(f"vnstock:tick:{sym}", json.dumps(tick))
    pipe.zadd("vnstock:ticks:all", {sym: ts})
    await pipe.execute()


async def _publish_kafka(kafka: AIOKafkaProducer, tick: dict):
    """Publish tick as Confluent Avro to Kafka."""
    if kafka is None or _avro_schema_id < 0:
        return
    try:
        key = tick["symbol"].encode("utf-8")
        value = _encode_avro(tick)
        await kafka.send(KAFKA_TOPIC, key=key, value=value)
        _stats["kafka_sent"] += 1
    except Exception as e:
        _stats["errors"] += 1
        logger.error("Kafka publish error: %s", e)


async def _handle_trade(r: aioredis.Redis, kafka: AIOKafkaProducer, trade: Trade):
    """Build live 1m candle from individual trade tick → Redis + Kafka."""
    try:
        sym = trade.symbol
        if not sym:
            return
        price = float(trade.price)
        qty = int(trade.quantity)
        if price <= 0:
            return

        now = int(time.time())
        bucket_sec = (now // 60) * 60
        bucket_ms = bucket_sec * 1000

        if sym not in _live_candles or _live_candles[sym]["time"] != bucket_ms:
            _live_candles[sym] = {
                "symbol": sym, "time": bucket_ms,
                "open": price, "high": price, "low": price, "close": price,
                "volume": qty, "resolution": "1", "source": "DNSE_WS",
            }
        else:
            c = _live_candles[sym]
            c["high"] = max(c["high"], price)
            c["low"] = min(c["low"], price)
            c["close"] = price
            c["volume"] += qty

        await _write_tick_redis(r, _live_candles[sym])
        await _publish_kafka(kafka, _live_candles[sym])
        _stats["ws_trades"] += 1
    except Exception as e:
        _stats["errors"] += 1
        logger.error("Trade handler error for %s: %s", getattr(trade, "symbol", "?"), e)


async def _handle_ohlc_1m(r: aioredis.Redis, kafka: AIOKafkaProducer, ohlc: Ohlc):
    """Authoritative 1m OHLC candle from server → Redis + Kafka."""
    try:
        sym = ohlc.symbol
        ts_ms = int(ohlc.time) * 1000 if int(ohlc.time) < 1e12 else int(ohlc.time)
        tick = {
            "symbol": sym, "time": ts_ms,
            "open": float(ohlc.open), "high": float(ohlc.high),
            "low": float(ohlc.low), "close": float(ohlc.close),
            "volume": int(ohlc.volume), "resolution": "1", "source": "DNSE_WS",
        }
        _live_candles[sym] = tick
        await _write_tick_redis(r, tick)
        await _publish_kafka(kafka, tick)
        _stats["ws_ohlc_1m"] += 1
    except Exception as e:
        _stats["errors"] += 1
        logger.error("OHLC 1m handler error for %s: %s", getattr(ohlc, "symbol", "?"), e)


async def _handle_ohlc_1d(r: aioredis.Redis, ohlc: Ohlc):
    """Daily OHLC → Redis daily data."""
    try:
        sym = ohlc.symbol
        daily = {
            "symbol": sym,
            "todayOpen": float(ohlc.open), "todayHigh": float(ohlc.high),
            "todayLow": float(ohlc.low), "todayClose": float(ohlc.close),
            "todayVol": int(ohlc.volume),
        }
        await r.set(f"vnstock:daily:{sym}", json.dumps(daily))
        _stats["ws_ohlc_1d"] += 1
    except Exception as e:
        _stats["errors"] += 1
        logger.error("OHLC 1D handler error for %s: %s", getattr(ohlc, "symbol", "?"), e)


async def _handle_secdef(r: aioredis.Redis, sd: SecurityDefinition):
    """Security definition → Redis secdef + daily changePct."""
    try:
        sym = sd.symbol
        secdef = {
            "basicPrice": float(sd.basicPrice),
            "ceilingPrice": float(sd.ceilingPrice),
            "floorPrice": float(sd.floorPrice),
        }
        await r.set(f"vnstock:secdef:{sym}", json.dumps(secdef))

        daily_raw = await r.get(f"vnstock:daily:{sym}")
        if daily_raw:
            daily = json.loads(daily_raw)
            if sd.basicPrice > 0:
                change_pct = (daily.get("todayClose", 0) - float(sd.basicPrice)) / float(sd.basicPrice) * 100
                daily["changePct"] = round(change_pct, 4)
                daily["prevClose"] = float(sd.basicPrice)
                await r.set(f"vnstock:daily:{sym}", json.dumps(daily))
        _stats["ws_secdef"] += 1
    except Exception as e:
        _stats["errors"] += 1
        logger.error("SecDef handler error for %s: %s", getattr(sd, "symbol", "?"), e)


async def _handle_quote(r: aioredis.Redis, quote: Quote):
    """Quote (bid/ask depth) → Redis."""
    try:
        sym = quote.symbol
        q = {
            "symbol": sym,
            "bid": [{"price": b.price, "qty": b.quantity} for b in (quote.bid or [])],
            "ask": [{"price": a.price, "qty": a.quantity} for a in (quote.offer or [])],
            "totalBidQtty": quote.totalBidQtty,
            "totalOfferQtty": quote.totalOfferQtty,
        }
        await r.set(f"vnstock:quote:{sym}", json.dumps(q))
        _stats["ws_quote"] += 1
    except Exception as e:
        _stats["errors"] += 1
        logger.error("Quote handler error for %s: %s", getattr(quote, "symbol", "?"), e)


async def ws_speed_layer(r: aioredis.Redis, kafka: AIOKafkaProducer,
                          symbol_lists: dict, stop_event: asyncio.Event):
    """Speed Layer: DNSE WebSocket → tick-by-tick real-time → Redis + Kafka.

    Auto-reconnects on failure. The TradingClient SDK handles transient
    disconnections internally; this outer loop handles catastrophic failures.
    """
    all_symbols = symbol_lists["all"]

    while not stop_event.is_set():
        try:
            client = TradingClient(
                api_key=DNSE_API_KEY, api_secret=DNSE_API_SECRET,
                base_url=DNSE_WS_URL, encoding=ENCODING,
                auto_reconnect=True, max_retries=100,
                heartbeat_interval=25.0, timeout=60.0,
            )

            # ── Callbacks ────────────────────────────────────
            def on_ohlc(ohlc: Ohlc):
                res = str(ohlc.resolution)
                if res in ("1", "1m"):
                    asyncio.create_task(_handle_ohlc_1m(r, kafka, ohlc))
                elif res in ("1D", "D", "1d"):
                    asyncio.create_task(_handle_ohlc_1d(r, ohlc))
                else:
                    asyncio.create_task(_handle_ohlc_1m(r, kafka, ohlc))

            def on_trade(trade: Trade):
                asyncio.create_task(_handle_trade(r, kafka, trade))

            def on_secdef(sd: SecurityDefinition):
                asyncio.create_task(_handle_secdef(r, sd))

            def on_quote(quote: Quote):
                asyncio.create_task(_handle_quote(r, quote))

            # ── Connect ──────────────────────────────────────
            logger.info("[Speed Layer] Connecting to DNSE WebSocket: %s", DNSE_WS_URL)
            await client.connect()
            logger.info("[Speed Layer] Connected! Session: %s", client._session_id)

            # ── Subscribe OHLC 1m + 1D (all symbols) ────────
            for i in range(0, len(all_symbols), SUB_CHUNK_SIZE):
                chunk = all_symbols[i:i + SUB_CHUNK_SIZE]
                await client.subscribe_ohlc(chunk, resolution="1",
                                             on_ohlc=on_ohlc, encoding=ENCODING)
            logger.info("[Speed Layer] Subscribed OHLC 1m: %d symbols", len(all_symbols))

            for i in range(0, len(all_symbols), SUB_CHUNK_SIZE):
                chunk = all_symbols[i:i + SUB_CHUNK_SIZE]
                await client.subscribe_ohlc(chunk, resolution="1D",
                                             on_ohlc=on_ohlc, encoding=ENCODING)
            logger.info("[Speed Layer] Subscribed OHLC 1D: %d symbols", len(all_symbols))

            # ── Subscribe Trades + SecDef + Quotes per board ─
            board_map = {
                "G1": symbol_lists["hose"],
                "G2": symbol_lists["hnx"],
                "G3": symbol_lists["upcom"],
            }
            for board_id, syms in board_map.items():
                if not syms:
                    continue
                for i in range(0, len(syms), SUB_CHUNK_SIZE):
                    chunk = syms[i:i + SUB_CHUNK_SIZE]
                    await client.subscribe_trades(
                        chunk, on_trade=on_trade,
                        encoding=ENCODING, board_id=board_id)
                logger.info("[Speed Layer] Subscribed Trades %s: %d symbols",
                            board_id, len(syms))

                for i in range(0, len(syms), SUB_CHUNK_SIZE):
                    chunk = syms[i:i + SUB_CHUNK_SIZE]
                    await client.subscribe_sec_def(
                        chunk, on_sec_def=on_secdef,
                        encoding=ENCODING, board_id=board_id)
                logger.info("[Speed Layer] Subscribed SecDef %s: %d symbols",
                            board_id, len(syms))

                for i in range(0, len(syms), SUB_CHUNK_SIZE):
                    chunk = syms[i:i + SUB_CHUNK_SIZE]
                    await client.subscribe_quotes(
                        chunk, on_quote=on_quote,
                        encoding=ENCODING, board_id=board_id)
                logger.info("[Speed Layer] Subscribed Quotes %s: %d symbols",
                            board_id, len(syms))

            logger.info("[Speed Layer] All subscriptions active — streaming tick-by-tick")

            # Keep alive until stop
            while not stop_event.is_set():
                await asyncio.sleep(1)

            await client.disconnect()
            logger.info("[Speed Layer] Disconnected gracefully")
            return

        except Exception as e:
            logger.error("[Speed Layer] WebSocket error: %s — reconnecting in 5s", e)
            _stats["errors"] += 1
            await asyncio.sleep(5)


# ═════════════════════════════════════════════════════════════════
#   BATCH LAYER — REST (finalized candles → Kafka → Iceberg)
# ═════════════════════════════════════════════════════════════════

def _fetch_finalized_candle(symbol: str) -> dict | None:
    """Fetch the last FINALIZED 1m candle (not the forming one) via REST."""
    now_ts = int(time.time())
    params = {
        "symbol": symbol, "resolution": "1",
        "from": now_ts - 3600, "to": now_ts,
    }
    try:
        resp = _get_session().get(DNSE_CHART_URL, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("t") or len(data["t"]) < 2:
            return None
        # Second-to-last candle = last finalized (current candle is still forming)
        idx = len(data["t"]) - 2
        candle_time_sec = int(data["t"][idx])
        return {
            "symbol": symbol, "time": candle_time_sec * 1000,
            "open": float(data["o"][idx]), "high": float(data["h"][idx]),
            "low": float(data["l"][idx]), "close": float(data["c"][idx]),
            "volume": int(data["v"][idx]),
            "resolution": "1", "source": "DNSE",
        }
    except Exception as e:
        logger.debug("REST fetch failed for %s: %s", symbol, e)
        return None


def _fetch_daily(symbol: str) -> dict | None:
    """Fetch daily candles for secdef (reference prices) — REST fallback."""
    now_ts = int(time.time())
    params = {
        "symbol": symbol, "resolution": "1D",
        "from": now_ts - 86400 * 10, "to": now_ts,
    }
    try:
        resp = _get_session().get(DNSE_CHART_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("t") or len(data["t"]) < 2:
            return None
        n = len(data["t"])
        prev_close = float(data["c"][n - 2])
        today_close = float(data["c"][n - 1])
        ceiling = round(prev_close * 1.07)
        floor_p = round(prev_close * 0.93)
        change_pct = ((today_close - prev_close) / prev_close * 100
                      if prev_close > 0 else 0)
        return {
            "symbol": symbol, "prevClose": prev_close,
            "todayOpen": float(data["o"][n - 1]), "todayClose": today_close,
            "todayHigh": float(data["h"][n - 1]), "todayLow": float(data["l"][n - 1]),
            "todayVol": int(data["v"][n - 1]),
            "changePct": round(change_pct, 4),
            "basicPrice": prev_close, "ceilingPrice": ceiling, "floorPrice": floor_p,
        }
    except Exception as e:
        logger.debug("REST daily fetch failed for %s: %s", symbol, e)
        return None


async def rest_batch_layer(r: aioredis.Redis, kafka: AIOKafkaProducer,
                            all_symbols: list[str], stop_event: asyncio.Event):
    """Batch Layer: REST → finalized candles every 60s → Kafka → Iceberg (Bronze).

    Also refreshes daily secdef data every 5 minutes as a fallback for the
    WebSocket SecurityDefinition subscription.
    """
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    last_daily_fetch = 0

    while not stop_event.is_set():
        cycle_start = time.time()

        if not is_market_open():
            await asyncio.sleep(60)
            continue

        try:
            # ─── Daily secdef refresh (every 5 min, REST fallback) ───
            if cycle_start - last_daily_fetch >= DAILY_REFRESH:
                logger.info("[Batch Layer] Fetching daily candles for secdef...")
                tasks = [loop.run_in_executor(executor, _fetch_daily, sym)
                         for sym in all_symbols]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                daily_list = [r_ for r_ in results if isinstance(r_, dict)]

                if daily_list:
                    pipe = r.pipeline()
                    for d in daily_list:
                        sym = d["symbol"]
                        secdef = {"basicPrice": d["basicPrice"],
                                  "ceilingPrice": d["ceilingPrice"],
                                  "floorPrice": d["floorPrice"]}
                        pipe.set(f"vnstock:secdef:{sym}", json.dumps(secdef))
                        pipe.set(f"vnstock:daily:{sym}", json.dumps(d))
                    await pipe.execute()
                    logger.info("[Batch Layer] Daily secdef: %d/%d symbols",
                                len(daily_list), len(all_symbols))
                last_daily_fetch = cycle_start

            # ─── Finalized 1m candles → Kafka ───────────────────
            logger.info("[Batch Layer] Fetching finalized 1m candles...")
            tasks = [loop.run_in_executor(executor, _fetch_finalized_candle, sym)
                     for sym in all_symbols]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            ticks = [r_ for r_ in results if isinstance(r_, dict)]

            if ticks and kafka and _avro_schema_id >= 0:
                for tick in ticks:
                    try:
                        key = tick["symbol"].encode("utf-8")
                        value = _encode_avro(tick)
                        await kafka.send(KAFKA_TOPIC, key=key, value=value)
                        _stats["kafka_sent"] += 1
                    except Exception as e:
                        _stats["errors"] += 1
                        logger.error("Kafka batch publish error: %s", e)
                _stats["rest_candles"] += len(ticks)

            elapsed = time.time() - cycle_start
            logger.info("[Batch Layer] Cycle: %d/%d finalized candles → Kafka (%.1fs)",
                        len(ticks), len(all_symbols), elapsed)

        except Exception as e:
            _stats["errors"] += 1
            logger.error("[Batch Layer] Error: %s", e)

        remaining = REST_INTERVAL - (time.time() - cycle_start)
        if remaining > 0:
            await asyncio.sleep(remaining)

    executor.shutdown(wait=False)


# ═════════════════════════════════════════════════════════════════
#   STATS REPORTER
# ═════════════════════════════════════════════════════════════════

async def _stats_reporter(stop_event: asyncio.Event):
    """Log aggregated stats every 60 seconds."""
    while not stop_event.is_set():
        await asyncio.sleep(60)
        uptime = time.time() - _stats["start_time"]
        logger.info(
            "Stats: trades=%d ohlc_1m=%d ohlc_1d=%d secdef=%d quote=%d "
            "rest=%d kafka=%d errors=%d uptime=%.0fs",
            _stats["ws_trades"], _stats["ws_ohlc_1m"], _stats["ws_ohlc_1d"],
            _stats["ws_secdef"], _stats["ws_quote"], _stats["rest_candles"],
            _stats["kafka_sent"], _stats["errors"], uptime,
        )


# ═════════════════════════════════════════════════════════════════
#   MAIN — Launch both layers concurrently
# ═════════════════════════════════════════════════════════════════

async def main():
    global _avro_schema_id
    _stats["start_time"] = time.time()

    if not DNSE_API_KEY or not DNSE_API_SECRET:
        logger.error("DNSE_API_KEY and DNSE_API_SECRET must be set")
        sys.exit(1)

    symbol_lists = _build_symbol_lists()
    all_symbols = symbol_lists["all"]
    if not all_symbols:
        logger.error("No symbols configured")
        sys.exit(1)

    # Register Avro schema
    try:
        _avro_schema_id = _register_avro_schema()
    except RuntimeError as e:
        logger.error("Schema Registry unavailable: %s — Kafka disabled", e)

    # Connect Redis (async)
    r = None
    for attempt in range(30):
        try:
            r = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT,
                               decode_responses=True)
            await r.ping()
            logger.info("Redis connected: %s:%d", REDIS_HOST, REDIS_PORT)
            break
        except Exception as e:
            logger.warning("Redis not ready (attempt %d/30): %s", attempt + 1, e)
            await asyncio.sleep(2)
    if r is None:
        logger.error("Cannot connect to Redis")
        sys.exit(1)

    # Connect Kafka (async)
    kafka = None
    for attempt in range(30):
        try:
            kafka = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                compression_type="gzip",
                linger_ms=50, max_batch_size=32768,
            )
            await kafka.start()
            logger.info("Kafka connected: %s", KAFKA_BOOTSTRAP)
            break
        except KafkaConnectionError:
            logger.warning("Kafka not ready (attempt %d/30)", attempt + 1)
            await asyncio.sleep(2)
    if kafka is None:
        logger.warning("Running WITHOUT Kafka — ticks will only go to Redis")

    logger.info("=" * 60)
    logger.info("  VVS Hybrid Producer — Speed Layer + Batch Layer")
    logger.info("=" * 60)
    logger.info("  Symbols: %d (HOSE=%d HNX=%d UPCOM=%d Deriv=%d Index=%d)",
                len(all_symbols), len(symbol_lists["hose"]),
                len(symbol_lists["hnx"]), len(symbol_lists["upcom"]),
                len(symbol_lists["deriv"]), len(symbol_lists["index"]))
    logger.info("  Speed Layer : WebSocket %s (encoding=%s)", DNSE_WS_URL, ENCODING)
    logger.info("  Batch Layer : REST every %ds → Kafka → Iceberg", REST_INTERVAL)
    logger.info("  Kafka       : %s → %s", KAFKA_BOOTSTRAP, KAFKA_TOPIC)
    logger.info("  Redis       : %s:%d", REDIS_HOST, REDIS_PORT)
    logger.info("=" * 60)

    # Graceful shutdown
    stop_event = asyncio.Event()

    def _request_shutdown():
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_shutdown)
        except NotImplementedError:
            pass  # Windows

    # Launch both layers + stats reporter
    ws_task    = asyncio.create_task(ws_speed_layer(r, kafka, symbol_lists, stop_event))
    rest_task  = asyncio.create_task(rest_batch_layer(r, kafka, all_symbols, stop_event))
    stats_task = asyncio.create_task(_stats_reporter(stop_event))

    try:
        await stop_event.wait()
    except asyncio.CancelledError:
        pass

    # Cleanup
    ws_task.cancel()
    rest_task.cancel()
    stats_task.cancel()

    if kafka:
        await kafka.stop()
    await r.aclose()
    logger.info("Producer stopped gracefully")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

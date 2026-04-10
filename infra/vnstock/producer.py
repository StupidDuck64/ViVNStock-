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
        hose = combined
        hnx = combined
        upcom = combined
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

# ─── Persistent reference data: prevClose / basicPrice per symbol ──
# Never cleared by buffer flush — holds the authoritative reference price
# so _handle_ohlc_1d can always compute changePct correctly.
_daily_persist: dict[str, dict] = {}     # symbol → {prevClose, basicPrice, ceilingPrice, floorPrice}

# ─── Write buffers: accumulate writes, flush periodically via pipeline ──
# This prevents 1000+ concurrent Redis connections from WS callbacks.
# Each callback just writes to the dict; a flush task pipelines all at once.
_tick_buffer: dict[str, dict] = {}       # symbol → tick dict (latest wins)
_daily_buffer: dict[str, dict] = {}      # symbol → daily dict (intraday OHLCV delta only)
_quote_buffer: dict[str, dict] = {}      # symbol → quote dict
_kafka_buffer: list[dict] = []           # list of ticks to publish
_buffer_lock = asyncio.Lock() if hasattr(asyncio, 'Lock') else None


async def _flush_buffers(r, kafka):
    """Flush all write buffers to Redis + Kafka in a single pipeline."""
    global _tick_buffer, _daily_buffer, _quote_buffer, _kafka_buffer

    # Swap buffers atomically
    ticks = _tick_buffer
    _tick_buffer = {}
    dailies = _daily_buffer
    _daily_buffer = {}
    quotes = _quote_buffer
    _quote_buffer = {}
    kafkas = _kafka_buffer
    _kafka_buffer = []

    if not ticks and not dailies and not quotes:
        return

    try:
        pipe = r.pipeline()
        for sym, tick in ticks.items():
            pipe.set(f"vnstock:tick:{sym}", json.dumps(tick))
            pipe.zadd("vnstock:ticks:all", {sym: tick["time"]})
        for sym, daily in dailies.items():
            # Merge with persistent reference data so prevClose/basicPrice
            # never get wiped from Redis by an intraday OHLCV-only update.
            merged = dict(_daily_persist.get(sym, {}))
            merged.update(daily)
            pipe.set(f"vnstock:daily:{sym}", json.dumps(merged))
        for sym, q in quotes.items():
            pipe.set(f"vnstock:quote:{sym}", json.dumps(q))
        await pipe.execute()
    except Exception as e:
        _stats["errors"] += 1
        if _stats["errors"] % 100 == 1:
            logger.error("Buffer flush Redis error: %s", e)

    # Kafka (non-blocking)
    if kafkas and kafka and _avro_schema_id >= 0:
        for tick in kafkas:
            try:
                key = tick["symbol"].encode("utf-8")
                value = _encode_avro(tick)
                await kafka.send(KAFKA_TOPIC, key=key, value=value)
                _stats["kafka_sent"] += 1
            except Exception as e:
                _stats["errors"] += 1


async def _buffer_flusher(r, kafka, stop_event: asyncio.Event):
    """Background task: flush write buffers every 200ms."""
    while not stop_event.is_set():
        await asyncio.sleep(0.2)
        await _flush_buffers(r, kafka)


# ═════════════════════════════════════════════════════════════════
#   SPEED LAYER — WebSocket (tick-by-tick real-time)
# ═════════════════════════════════════════════════════════════════

async def _write_tick_redis(r: aioredis.Redis, tick: dict):
    """Buffer tick write — flushed every 200ms by _buffer_flusher."""
    _tick_buffer[tick["symbol"]] = tick


async def _publish_kafka(kafka: AIOKafkaProducer, tick: dict):
    """Buffer Kafka publish — flushed every 200ms by _buffer_flusher."""
    if kafka is None or _avro_schema_id < 0:
        return
    _kafka_buffer.append(tick)


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
        # Guard: reject T-1 replay data (timestamp older than 5 minutes)
        ts_sec = ts_ms // 1000 if ts_ms > 1e12 else ts_ms
        if abs(time.time() - ts_sec) > 300:
            return
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
    """Daily OHLC → buffer intraday OHLCV; compute changePct from persistent reference."""
    try:
        sym = ohlc.symbol
        daily = _daily_buffer.get(sym, {})
        today_close = float(ohlc.close)
        daily.update({
            "symbol": sym,
            "todayOpen": float(ohlc.open), "todayHigh": float(ohlc.high),
            "todayLow": float(ohlc.low), "todayClose": today_close,
            "todayVol": int(ohlc.volume),
        })
        # Always read prevClose from persistent store (survives buffer flush cycles)
        ref = _daily_persist.get(sym, {}).get("prevClose", 0)
        if ref and ref > 0:
            daily["changePct"] = round(((today_close - ref) / ref) * 100, 4)
        _daily_buffer[sym] = daily
        _stats["ws_ohlc_1d"] += 1
    except Exception as e:
        _stats["errors"] += 1
        logger.error("OHLC 1D handler error for %s: %s", getattr(ohlc, "symbol", "?"), e)


async def _handle_secdef(r: aioredis.Redis, sd: SecurityDefinition):
    """Security definition from exchange WS → Redis secdef (initial fill only).

    Writes the official exchange reference prices (basicPrice / ceilingPrice / floorPrice)
    coming directly from HOSE/HNX/UPCOM via DNSE WS. Used as an initial fill so that
    changePct is available immediately on startup before the REST batch layer runs.
    The REST batch layer (_fetch_daily, every 5 min) overwrites with confirmed values.
    """
    try:
        sym = sd.symbol
        if not sym:
            return
        basic = float(sd.basicPrice) if sd.basicPrice else 0.0
        if basic <= 0:
            return
        ceiling = float(sd.ceilingPrice) if sd.ceilingPrice else round(basic * 1.07, 2)
        floor_p = float(sd.floorPrice) if sd.floorPrice else round(basic * 0.93, 2)

        secdef_data = {
            "symbol": sym,
            "basicPrice": basic,
            "ceilingPrice": ceiling,
            "floorPrice": floor_p,
        }
        # Populate persistent store — REST batch overwrites this every 5 min with confirmed data
        if sym not in _daily_persist:
            _daily_persist[sym] = {}
        _daily_persist[sym].update({
            "prevClose": basic, "basicPrice": basic,
            "ceilingPrice": ceiling, "floorPrice": floor_p,
        })
        await r.set(f"vnstock:secdef:{sym}", json.dumps(secdef_data))
        _stats["ws_secdef"] += 1
    except Exception as e:
        _stats["errors"] += 1
        logger.error("SecDef handler error for %s: %s", getattr(sd, "symbol", "?"), e)


async def _handle_quote(r: aioredis.Redis, quote: Quote):
    """Quote (bid/ask depth) → buffer."""
    try:
        sym = quote.symbol
        q = {
            "symbol": sym,
            "bid": [{"price": b.price, "qty": b.quantity} for b in (quote.bid or [])],
            "ask": [{"price": a.price, "qty": a.quantity} for a in (quote.offer or [])],
            "totalBidQtty": quote.totalBidQtty,
            "totalOfferQtty": quote.totalOfferQtty,
        }
        _quote_buffer[sym] = q
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
                auto_reconnect=False, max_retries=100,
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

            # Keep alive until stop — monitor connection health
            while not stop_event.is_set():
                await asyncio.sleep(1)
                # Detect dead _message_handler or lost connection
                if hasattr(client, '_message_handler_task') and client._message_handler_task.done():
                    logger.warning("[Speed Layer] Message handler task died — forcing full reconnect")
                    break
                if not client._connection.is_connected:
                    logger.warning("[Speed Layer] Connection lost — forcing full reconnect")
                    break

            try:
                await client.disconnect()
            except Exception:
                pass
            if stop_event.is_set():
                logger.info("[Speed Layer] Disconnected gracefully")
                return
            logger.info("[Speed Layer] Reconnecting with fresh TradingClient...")

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
        
        # A candle of resolution 1m is fully finalized after its start + 60s
        idx = len(data["t"]) - 1
        last_t = int(data["t"][idx])
        if now_ts < last_t + 60:
            idx -= 1

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
        import datetime
        import pytz
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        now_vn = datetime.datetime.now(vn_tz).date()
        last_t = int(data["t"][-1])
        last_date = datetime.datetime.fromtimestamp(last_t, vn_tz).date()
        
        n = len(data["t"])
        if last_date >= now_vn:
            # We are in the current trading day
            prev_close = float(data["c"][n - 2]) if n >= 2 else float(data["c"][n - 1])
            today_close = float(data["c"][n - 1])
            today_open = float(data["o"][n - 1])
            today_high = float(data["h"][n - 1])
            today_low = float(data["l"][n - 1])
            today_vol = int(data["v"][n - 1])
        else:
            # Market hasn't started yet today, so the latest data is yesterday
            prev_close = float(data["c"][n - 1])
            today_close = prev_close
            today_open = float(data["c"][n - 1])
            today_high = float(data["h"][n - 1])
            today_low = float(data["l"][n - 1])
            today_vol = 0

        ceiling = round(prev_close * 1.07, 2)
        floor_p = round(prev_close * 0.93, 2)
        change_pct = ((today_close - prev_close) / prev_close * 100
                      if prev_close > 0 else 0)
        return {
            "symbol": symbol, "prevClose": prev_close,
            "todayOpen": today_open, "todayClose": today_close,
            "todayHigh": today_high, "todayLow": today_low,
            "todayVol": today_vol,
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

    first_run = True
    while not stop_event.is_set():
        cycle_start = time.time()

        if not is_market_open() and not first_run:
            await asyncio.sleep(60)
            continue
        first_run = False

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
                        # Update persistent store — REST values are authoritative,
                        # override any earlier WS-secdef fill.
                        _daily_persist[sym] = {
                            "prevClose": d["prevClose"],
                            "basicPrice": d["basicPrice"],
                            "ceilingPrice": d["ceilingPrice"],
                            "floorPrice": d["floorPrice"],
                        }
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

            if ticks:
                # Batch MGET existing tick timestamps to avoid 1000 individual GET calls
                tick_keys = [f"vnstock:tick:{t['symbol']}" for t in ticks]
                existing_raws = await r.mget(tick_keys)
                existing_map = {}
                for i, raw in enumerate(existing_raws):
                    if raw:
                        existing_map[ticks[i]["symbol"]] = json.loads(raw)

                pipe = r.pipeline()
                for tick in ticks:
                    sym = tick["symbol"]
                    existing = existing_map.get(sym)
                    if existing:
                        et = existing.get("time", 0)
                        et = et // 1000 if et > 1e12 else et
                        tt = tick["time"] // 1000 if tick["time"] > 1e12 else tick["time"]
                        if tt <= et:
                            continue  # WS data is newer, skip
                    tick_for_redis = dict(tick, source="DNSE")
                    pipe.set(f"vnstock:tick:{sym}", json.dumps(tick_for_redis))
                    pipe.zadd("vnstock:ticks:all", {sym: tick["time"]})
                await pipe.execute()

                # Batch MGET daily data, update todayClose from tick prices
                daily_keys = [f"vnstock:daily:{t['symbol']}" for t in ticks]
                daily_raws = await r.mget(daily_keys)
                daily_pipe = r.pipeline()
                for i, tick in enumerate(ticks):
                    raw = daily_raws[i]
                    if not raw:
                        continue
                    daily = json.loads(raw)
                    tc = float(tick["close"])
                    th = float(tick["high"])
                    tl = float(tick["low"])
                    updated = False
                    if tc > 0 and tc != daily.get("todayClose", 0):
                        daily["todayClose"] = tc
                        updated = True
                    if th > daily.get("todayHigh", 0):
                        daily["todayHigh"] = th
                        updated = True
                    if tl > 0 and (daily.get("todayLow", 0) <= 0 or tl < daily.get("todayLow", 999999)):
                        daily["todayLow"] = tl
                        updated = True
                    if updated:
                        ref = daily.get("prevClose", 0) or daily.get("basicPrice", 0)
                        if ref > 0:
                            daily["changePct"] = round(((daily["todayClose"] - ref) / ref) * 100, 4)
                        daily_pipe.set(f"vnstock:daily:{tick['symbol']}", json.dumps(daily))
                await daily_pipe.execute()

                if kafka and _avro_schema_id >= 0:
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

    # Connect Redis (async) — use connection pool to prevent port exhaustion
    # With 1000+ symbols each generating ticks, unlimited connections will exhaust
    # ephemeral ports (~65k). Pool of 32 connections is plenty for all operations.
    r = None
    for attempt in range(30):
        try:
            pool = aioredis.ConnectionPool(
                host=REDIS_HOST, port=REDIS_PORT,
                decode_responses=True, max_connections=32,
            )
            r = aioredis.Redis(connection_pool=pool)
            await r.ping()
            logger.info("Redis connected: %s:%d (pool=32)", REDIS_HOST, REDIS_PORT)
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

    # Launch both layers + stats reporter + buffer flusher
    flush_task = asyncio.create_task(_buffer_flusher(r, kafka, stop_event))
    ws_task    = asyncio.create_task(ws_speed_layer(r, kafka, symbol_lists, stop_event))
    rest_task  = asyncio.create_task(rest_batch_layer(r, kafka, all_symbols, stop_event))
    stats_task = asyncio.create_task(_stats_reporter(stop_event))

    try:
        await stop_event.wait()
    except asyncio.CancelledError:
        pass

    # Cleanup
    flush_task.cancel()
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

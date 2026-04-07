"""
VVS Market Data Producer — DNSE OpenAPI WebSocket → Kafka + Redis

Connects to DNSE OpenAPI WebSocket gateway (wss://ws-openapi.dnse.com.vn)
and streams real-time market data to Kafka + Redis.

Replaces REST polling approach (15s latency) with true WebSocket streaming (<100ms).

Data flow (Lambda Architecture — Speed Layer):
  DNSE WebSocket → Producer → Kafka topic (vnstock.ohlc.realtime)
                             → Redis (low-latency frontend serving)

Subscriptions:
  - OHLC 1m candles       → Kafka + Redis vnstock:tick:{SYMBOL}
  - OHLC 1D candles       → Redis vnstock:daily:{SYMBOL}
  - SecurityDefinition     → Redis vnstock:secdef:{SYMBOL}
  - Quote (BBO)            → Redis vnstock:quote:{SYMBOL}

Kafka topic:
  vnstock.ohlc.realtime → JSON: {symbol, time, open, high, low, close, volume, resolution, source}

Redis key structure:
  vnstock:tick:{SYMBOL}   → JSON: latest 1m candle
  vnstock:ticks:all       → Sorted Set (member=symbol, score=timestamp)
  vnstock:secdef:{SYMBOL} → JSON: {basicPrice, ceilingPrice, floorPrice}
  vnstock:daily:{SYMBOL}  → JSON: daily OHLCV + changePct
  vnstock:quote:{SYMBOL}  → JSON: bid/ask depth
"""

import asyncio
import json
import logging
import os
import signal
import sys
import io
import struct
import time

import fastavro
import redis.asyncio as aioredis
import requests
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

from trading_websocket import TradingClient
from trading_websocket.models import Ohlc, SecurityDefinition, Quote, Trade

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("vnstock_producer_ws")

# ─── Configuration ───────────────────────────────────────────────
REDIS_HOST       = os.getenv("REDIS_HOST", "redis")
REDIS_PORT       = int(os.getenv("REDIS_PORT", "6379"))
KAFKA_BOOTSTRAP  = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC      = os.getenv("KAFKA_TOPIC", "vnstock.ohlc.realtime")
SCHEMA_REGISTRY  = os.getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")

DNSE_API_KEY     = os.getenv("DNSE_API_KEY", "")
DNSE_API_SECRET  = os.getenv("DNSE_API_SECRET", "")
DNSE_WS_URL      = os.getenv("DNSE_WS_URL", "wss://ws-openapi.dnse.com.vn")
ENCODING         = os.getenv("WS_ENCODING", "json")  # "json" or "msgpack"

# Symbols per exchange (for board-specific subscriptions)
SYMBOLS_HOSE_RAW   = os.getenv("VNSTOCK_SYMBOLS_HOSE", "")
SYMBOLS_HNX_RAW    = os.getenv("VNSTOCK_SYMBOLS_HNX", "")
SYMBOLS_UPCOM_RAW  = os.getenv("VNSTOCK_SYMBOLS_UPCOM", "")
SYMBOLS_DERIV_RAW  = os.getenv("VNSTOCK_SYMBOLS_DERIVATIVE", "")
SYMBOLS_INDEX_RAW  = os.getenv("VNSTOCK_SYMBOLS_INDEX", "")

# Combined flat list
SYMBOLS_ALL_RAW = os.getenv("SYMBOLS", "")

# Max symbols per subscription message (chunking for safety)
SUB_CHUNK_SIZE = int(os.getenv("SUB_CHUNK_SIZE", "500"))


def _parse_symbols(raw: str) -> list[str]:
    """Parse comma-separated symbol string into a clean list."""
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


# ─── Avro schema (must match streaming.py TICK_SCHEMA) ───────────────
_OHLC_AVRO_SCHEMA = fastavro.parse_schema({
    "type": "record",
    "name": "VnstockOhlc",
    "namespace": "vn.vnstock",
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
_avro_schema_id: int = -1  # set by _register_avro_schema()


def _register_avro_schema() -> int:
    """Register OHLC Avro schema with Confluent Schema Registry, return schema_id."""
    subject = f"{KAFKA_TOPIC}-value"
    url = f"{SCHEMA_REGISTRY}/subjects/{subject}/versions"
    payload = {"schema": json.dumps({
        "type": "record",
        "name": "VnstockOhlc",
        "namespace": "vn.vnstock",
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
            import time as _t; _t.sleep(2)
    raise RuntimeError(f"Cannot register Avro schema after 30 attempts")


def _encode_avro(record: dict) -> bytes:
    """Serialize a tick record to Confluent Avro wire format."""
    buf = io.BytesIO()
    buf.write(b'\x00')
    buf.write(struct.pack('>I', _avro_schema_id))
    fastavro.schemaless_writer(buf, _OHLC_AVRO_SCHEMA, record)
    return buf.getvalue()


def _build_symbol_lists():
    """Build per-board and combined symbol lists from env vars."""
    hose = _parse_symbols(SYMBOLS_HOSE_RAW)
    hnx = _parse_symbols(SYMBOLS_HNX_RAW)
    upcom = _parse_symbols(SYMBOLS_UPCOM_RAW)
    deriv = _parse_symbols(SYMBOLS_DERIV_RAW)
    index_syms = _parse_symbols(SYMBOLS_INDEX_RAW)

    # If per-board vars are empty, fall back to combined SYMBOLS var
    all_symbols = hose + hnx + upcom + deriv + index_syms
    if not all_symbols:
        all_symbols = _parse_symbols(SYMBOLS_ALL_RAW)

    return {
        "hose": hose,       # Board G1
        "hnx": hnx,         # Board G2
        "upcom": upcom,     # Board G3
        "deriv": deriv,     # Board G4+
        "index": index_syms,
        "all": all_symbols,
    }


# ─── Counters ────────────────────────────────────────────────────
_stats = {
    "ohlc_1m": 0,
    "ohlc_1d": 0,
    "secdef": 0,
    "quote": 0,
    "trade": 0,
    "kafka_sent": 0,
    "errors": 0,
    "start_time": 0,
}


# ─── Redis Writers ───────────────────────────────────────────────

async def write_ohlc_tick(r: aioredis.Redis, ohlc: Ohlc):
    """Write 1m OHLC candle to Redis as a tick update."""
    sym = ohlc.symbol
    # Time: SDK returns epoch seconds → convert to ms for backward compatibility
    ts_ms = int(ohlc.time) * 1000 if int(ohlc.time) < 1e12 else int(ohlc.time)

    tick = {
        "symbol": sym,
        "time": ts_ms,
        "open": float(ohlc.open),
        "high": float(ohlc.high),
        "low": float(ohlc.low),
        "close": float(ohlc.close),
        "volume": int(ohlc.volume),
        "resolution": str(ohlc.resolution),
        "source": "DNSE",
    }
    pipe = r.pipeline()
    pipe.set(f"vnstock:tick:{sym}", json.dumps(tick))
    pipe.zadd("vnstock:ticks:all", {sym: ts_ms})
    await pipe.execute()
    return tick


async def write_ohlc_daily(r: aioredis.Redis, ohlc: Ohlc):
    """Write 1D OHLC candle to Redis as daily data."""
    sym = ohlc.symbol
    daily = {
        "symbol": sym,
        "todayOpen": float(ohlc.open),
        "todayHigh": float(ohlc.high),
        "todayLow": float(ohlc.low),
        "todayClose": float(ohlc.close),
        "todayVol": int(ohlc.volume),
    }
    await r.set(f"vnstock:daily:{sym}", json.dumps(daily))


async def write_secdef(r: aioredis.Redis, sd: SecurityDefinition):
    """Write security definition (reference prices) to Redis."""
    sym = sd.symbol
    secdef = {
        "basicPrice": float(sd.basicPrice),
        "ceilingPrice": float(sd.ceilingPrice),
        "floorPrice": float(sd.floorPrice),
    }
    await r.set(f"vnstock:secdef:{sym}", json.dumps(secdef))

    # Also compute changePct if we have daily data
    daily_raw = await r.get(f"vnstock:daily:{sym}")
    if daily_raw:
        daily = json.loads(daily_raw)
        if sd.basicPrice > 0:
            change_pct = (daily.get("todayClose", 0) - float(sd.basicPrice)) / float(sd.basicPrice) * 100
            daily["changePct"] = round(change_pct, 4)
            daily["prevClose"] = float(sd.basicPrice)
            await r.set(f"vnstock:daily:{sym}", json.dumps(daily))


async def write_quote(r: aioredis.Redis, quote: Quote):
    """Write bid/ask quote data to Redis."""
    sym = quote.symbol
    q = {
        "symbol": sym,
        "bid": [{"price": b.price, "qty": b.quantity} for b in (quote.bid or [])],
        "ask": [{"price": a.price, "qty": a.quantity} for a in (quote.offer or [])],
        "totalBidQtty": quote.totalBidQtty,
        "totalOfferQtty": quote.totalOfferQtty,
    }
    await r.set(f"vnstock:quote:{sym}", json.dumps(q))


# ─── Kafka Writer ────────────────────────────────────────────────

async def publish_to_kafka(producer: AIOKafkaProducer, tick: dict):
    """Publish a tick to Kafka as Confluent Avro."""
    if producer is None or _avro_schema_id < 0:
        return
    try:
        key = tick["symbol"].encode("utf-8")
        value = _encode_avro(tick)
        await producer.send(KAFKA_TOPIC, key=key, value=value)
        _stats["kafka_sent"] += 1
    except Exception as e:
        _stats["errors"] += 1
        logger.error("Kafka publish error: %s", e)


# ─── Main Producer ───────────────────────────────────────────────

async def main():
    global _avro_schema_id
    _stats["start_time"] = time.time()

    if not DNSE_API_KEY or not DNSE_API_SECRET:
        logger.error("DNSE_API_KEY and DNSE_API_SECRET must be set")
        sys.exit(1)

    # Register Avro schema before starting Kafka producer
    try:
        _avro_schema_id = _register_avro_schema()
    except RuntimeError as e:
        logger.error("Schema Registry unavailable: %s — Kafka publishing will be DISABLED", e)
        _avro_schema_id = -1

    symbol_lists = _build_symbol_lists()
    all_symbols = symbol_lists["all"]
    if not all_symbols:
        logger.error("No symbols configured")
        sys.exit(1)

    logger.info("VVS WebSocket Producer starting...")
    logger.info("  Symbols: %d (HOSE=%d, HNX=%d, UPCOM=%d, Deriv=%d, Index=%d)",
                len(all_symbols),
                len(symbol_lists["hose"]),
                len(symbol_lists["hnx"]),
                len(symbol_lists["upcom"]),
                len(symbol_lists["deriv"]),
                len(symbol_lists["index"]))
    logger.info("  WebSocket: %s (encoding=%s)", DNSE_WS_URL, ENCODING)
    logger.info("  Kafka: %s → %s", KAFKA_BOOTSTRAP, KAFKA_TOPIC)
    logger.info("  Redis: %s:%d", REDIS_HOST, REDIS_PORT)

    # ── Connect to Redis ─────────────────────────────────────────
    r = None
    for attempt in range(30):
        try:
            r = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            await r.ping()
            logger.info("Redis connected: %s:%d", REDIS_HOST, REDIS_PORT)
            break
        except Exception as e:
            logger.warning("Redis not ready (attempt %d/30): %s", attempt + 1, e)
            await asyncio.sleep(2)
    if r is None:
        logger.error("Cannot connect to Redis after 30 attempts")
        sys.exit(1)

    # ── Connect to Kafka ─────────────────────────────────────────
    kafka_producer = None
    for attempt in range(30):
        try:
            kafka_producer = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                compression_type="lz4",
                linger_ms=50,
                max_batch_size=32768,
            )
            await kafka_producer.start()
            logger.info("Kafka producer connected: %s", KAFKA_BOOTSTRAP)
            break
        except KafkaConnectionError:
            logger.warning("Kafka not ready (attempt %d/30)", attempt + 1)
            await asyncio.sleep(2)
    if kafka_producer is None:
        logger.warning("Running WITHOUT Kafka — ticks will only go to Redis")

    # ── Connect to DNSE WebSocket ────────────────────────────────
    client = TradingClient(
        api_key=DNSE_API_KEY,
        api_secret=DNSE_API_SECRET,
        base_url=DNSE_WS_URL,
        encoding=ENCODING,
        auto_reconnect=True,
        max_retries=100,
        heartbeat_interval=25.0,
        timeout=60.0,
    )

    # ── Callbacks ────────────────────────────────────────────────

    def on_ohlc(ohlc: Ohlc):
        """Handle incoming OHLC candle (1m or 1D)."""
        resolution = str(ohlc.resolution)
        if resolution in ("1", "1m"):
            _stats["ohlc_1m"] += 1
            asyncio.create_task(_handle_ohlc_1m(r, kafka_producer, ohlc))
        elif resolution in ("1D", "D", "1d"):
            _stats["ohlc_1d"] += 1
            asyncio.create_task(_handle_ohlc_1d(r, ohlc))
        else:
            # Other resolutions — still write to Redis as tick
            _stats["ohlc_1m"] += 1
            asyncio.create_task(_handle_ohlc_1m(r, kafka_producer, ohlc))

    def on_secdef(sd: SecurityDefinition):
        _stats["secdef"] += 1
        asyncio.create_task(write_secdef(r, sd))

    def on_quote(quote: Quote):
        _stats["quote"] += 1
        asyncio.create_task(write_quote(r, quote))

    # ── Connect & Subscribe ──────────────────────────────────────
    logger.info("Connecting to DNSE WebSocket gateway...")
    await client.connect()
    logger.info("Connected! Session ID: %s", client._session_id)

    # Subscribe OHLC 1m (all symbols, single channel, chunked)
    ohlc_symbols = all_symbols[:]
    for i in range(0, len(ohlc_symbols), SUB_CHUNK_SIZE):
        chunk = ohlc_symbols[i:i + SUB_CHUNK_SIZE]
        await client.subscribe_ohlc(chunk, resolution="1", on_ohlc=on_ohlc, encoding=ENCODING)
        logger.info("Subscribed OHLC 1m: symbols %d-%d/%d",
                     i + 1, min(i + SUB_CHUNK_SIZE, len(ohlc_symbols)), len(ohlc_symbols))

    # Subscribe OHLC 1D (all symbols for daily data)
    for i in range(0, len(ohlc_symbols), SUB_CHUNK_SIZE):
        chunk = ohlc_symbols[i:i + SUB_CHUNK_SIZE]
        await client.subscribe_ohlc(chunk, resolution="1D", on_ohlc=on_ohlc, encoding=ENCODING)
    logger.info("Subscribed OHLC 1D: %d symbols", len(ohlc_symbols))

    # Subscribe SecurityDefinition per board
    board_map = {
        "G1": symbol_lists["hose"],
        "G2": symbol_lists["hnx"],
        "G3": symbol_lists["upcom"],
    }
    for board_id, syms in board_map.items():
        if syms:
            for i in range(0, len(syms), SUB_CHUNK_SIZE):
                chunk = syms[i:i + SUB_CHUNK_SIZE]
                await client.subscribe_sec_def(chunk, on_sec_def=on_secdef, encoding=ENCODING, board_id=board_id)
            logger.info("Subscribed SecDef %s: %d symbols", board_id, len(syms))

    # Subscribe Quotes per board (bid/ask data)
    for board_id, syms in board_map.items():
        if syms:
            for i in range(0, len(syms), SUB_CHUNK_SIZE):
                chunk = syms[i:i + SUB_CHUNK_SIZE]
                await client.subscribe_quotes(chunk, on_quote=on_quote, encoding=ENCODING, board_id=board_id)
            logger.info("Subscribed Quotes %s: %d symbols", board_id, len(syms))

    logger.info("All subscriptions active — streaming real-time data")

    # ── Stats reporter (periodic) ────────────────────────────────
    stop_event = asyncio.Event()

    def _shutdown():
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    # Stats logging loop
    last_stats_log = time.time()
    stats_interval = 60  # log stats every 60 seconds

    try:
        while not stop_event.is_set():
            await asyncio.sleep(1)

            # Periodic stats logging
            now = time.time()
            if now - last_stats_log >= stats_interval:
                uptime = now - _stats["start_time"]
                logger.info(
                    "Stats: ohlc_1m=%d ohlc_1d=%d secdef=%d quote=%d kafka=%d errors=%d uptime=%.0fs healthy=%s",
                    _stats["ohlc_1m"], _stats["ohlc_1d"], _stats["secdef"],
                    _stats["quote"], _stats["kafka_sent"], _stats["errors"],
                    uptime, client.is_healthy,
                )
                last_stats_log = now
    except asyncio.CancelledError:
        pass

    # ── Graceful shutdown ────────────────────────────────────────
    logger.info("Shutting down...")
    await client.disconnect()
    if kafka_producer:
        await kafka_producer.stop()
    await r.aclose()
    logger.info("Producer stopped gracefully")


async def _handle_ohlc_1m(r: aioredis.Redis, kafka_producer, ohlc: Ohlc):
    """Process 1m OHLC: write to Redis + publish to Kafka."""
    try:
        tick = await write_ohlc_tick(r, ohlc)
        await publish_to_kafka(kafka_producer, tick)
    except Exception as e:
        _stats["errors"] += 1
        logger.error("Error processing OHLC 1m for %s: %s", ohlc.symbol, e)


async def _handle_ohlc_1d(r: aioredis.Redis, ohlc: Ohlc):
    """Process 1D OHLC: write daily data to Redis."""
    try:
        await write_ohlc_daily(r, ohlc)
    except Exception as e:
        _stats["errors"] += 1
        logger.error("Error processing OHLC 1D for %s: %s", ohlc.symbol, e)


if __name__ == "__main__":
    # Windows compat: use WindowsSelectorEventLoopPolicy if needed
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

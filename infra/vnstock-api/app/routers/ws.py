import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.connections import get_redis

logger = logging.getLogger("vnstock-api.ws")

router = APIRouter(tags=["websocket"])

POLL_INTERVAL = 0.2       # Poll Redis every 200ms (Speed Layer pushes trades in real-time)
HEARTBEAT_INTERVAL = 60   # Send ping every 30s (counter increments at 2x rate now)


@router.websocket("/api/ws/stream")
async def ws_stream(websocket: WebSocket, symbol: str = Query("VCB")):
    await websocket.accept()
    sym = symbol.strip().upper()
    last_sent_data = None        # Full candle dict for change detection
    last_quote_hash = None
    heartbeat_counter = 0

    logger.info("WS connected: %s (remote=%s)", sym, websocket.client)

    async def listen_for_commands():
        """Listen for client commands (subscribe to switch symbol, pong for heartbeat)."""
        nonlocal sym, last_sent_data
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                    if msg.get("type") == "subscribe" and msg.get("symbol"):
                        old_sym = sym
                        sym = msg["symbol"].strip().upper()
                        last_sent_data = None  # Reset on symbol switch
                        logger.info("WS switch: %s → %s", old_sym, sym)
                    # pong — just acknowledge, no action needed
                except json.JSONDecodeError:
                    pass
        except (WebSocketDisconnect, Exception):
            pass

    # Run listener concurrently with the sender loop
    listener_task = asyncio.create_task(listen_for_commands())

    try:
        while True:
            r = await get_redis()

            # ── Build live candle from Redis tick data ──
            tick_raw = await r.get(f"vnstock:tick:{sym}")
            if tick_raw:
                tick = json.loads(tick_raw)

                # Normalize time → seconds for Lightweight Charts
                if tick.get("time") and tick["time"] > 1_000_000_000_000:
                    tick["time"] = tick["time"] // 1000

                # Detect ANY content change: close, high, low, volume, OR time
                # This is the key difference from old code which only checked timestamp
                candle_key = (tick.get("time"), tick.get("close"), tick.get("high"),
                              tick.get("low"), tick.get("volume"))
                if candle_key != last_sent_data:
                    await websocket.send_json({"type": "tick", "data": tick})
                    last_sent_data = candle_key

            # ── Poll quote data (every 6th cycle ≈ 3s) ──
            if heartbeat_counter % 6 == 0:
                quote_raw = await r.get(f"vnstock:quote:{sym}")
                if quote_raw:
                    qhash = hash(quote_raw)
                    if qhash != last_quote_hash:
                        await websocket.send_json({"type": "quote", "data": json.loads(quote_raw)})
                        last_quote_hash = qhash

            # ── Heartbeat ──
            heartbeat_counter += 1
            if heartbeat_counter >= HEARTBEAT_INTERVAL:
                await websocket.send_json({"type": "ping"})
                heartbeat_counter = 0

            await asyncio.sleep(POLL_INTERVAL)

    except WebSocketDisconnect:
        logger.info("WS disconnected: %s", sym)
    except Exception as e:
        logger.error("WS error for %s: %s", sym, e)
    finally:
        listener_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass

/**
 * api.js — VNStock API Service Layer
 *
 * All frontend data access goes through this module.
 * FastAPI backend is behind nginx reverse proxy (/api/).
 *
 * WebSocket Protocol (bidirectional):
 *   Server → Client:
 *     {type: "tick",  data: {symbol, time, open, high, low, close, volume}}
 *     {type: "quote", data: {symbol, bid[], offer[], ...}}
 *     {type: "ping"}
 *   Client → Server:
 *     {type: "subscribe", symbol: "HPG"}   — switch symbol without reconnect
 *     {type: "pong"}                        — reply heartbeat
 */

const API = "/api";

// Vietnam timezone offset (UTC+7) in seconds — lightweight-charts uses
// business-day / UTC timestamps, so we shift all times to display Vietnam local time.
export const VN_OFFSET = 7 * 3600;

function wsBaseUrl() {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${API}`;
}

// ─── History (Iceberg via Trino) ──────────────────────────────
export async function fetchHistory(symbol, interval = "1m", limit = 500, endTime = null) {
  let url = `${API}/history?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&limit=${limit}`;
  if (endTime) url += `&end_time=${endTime}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`History API ${res.status}: ${res.statusText}`);
  const data = await res.json();
  // Shift UTC timestamps to Vietnam local time for chart display
  return data.map(c => ({ ...c, time: c.time + VN_OFFSET }));
}

// ─── Realtime (Redis) ─────────────────────────────────────────
export async function fetchRealtime(symbol) {
  const res = await fetch(`${API}/realtime?symbol=${encodeURIComponent(symbol)}`);
  if (!res.ok) throw new Error(`Realtime API ${res.status}`);
  return res.json();
}

export async function fetchAllRealtime() {
  const res = await fetch(`${API}/realtime`);
  if (!res.ok) throw new Error(`Realtime API ${res.status}`);
  return res.json();
}

// ─── Realtime Summary (batch: tick + quote + secdef + expected) ─
export async function fetchSummary(symbol) {
  const res = await fetch(`${API}/realtime/summary?symbol=${encodeURIComponent(symbol)}`);
  if (!res.ok) throw new Error(`Summary API ${res.status}`);
  return res.json();
}

// ─── Daily (pre-computed changePct from daily candles) ────────
export async function fetchAllDaily() {
  const res = await fetch(`${API}/realtime/daily`);
  if (!res.ok) throw new Error(`Daily API ${res.status}`);
  return res.json();
}

// ─── Batch quotes (all bid/ask snapshots in Redis) ────────────
export async function fetchAllQuotes() {
  const res = await fetch(`${API}/realtime/quote/all`);
  if (!res.ok) throw new Error(`Quote batch API ${res.status}`);
  return res.json(); // { symbol: { bid:[], ask:[] } }
}

// ─── News (Redis) ─────────────────────────────────────────────
export async function fetchNews(limit = 20) {
  const res = await fetch(`${API}/news?limit=${limit}`);
  if (!res.ok) throw new Error(`News API ${res.status}`);
  return res.json();
}

// ─── Symbols ──────────────────────────────────────────────────
export async function fetchSymbols() {
  const res = await fetch(`${API}/symbols`);
  if (!res.ok) throw new Error(`Symbols API ${res.status}`);
  return res.json();
}

// ─── WebSocket (bidirectional protocol) ───────────────────────

/**
 * Open a WebSocket connection for real-time streaming.
 *
 * @param {string}   symbol   - Initial symbol (VCB, HPG, ...)
 * @param {Function} onTick   - Callback when receiving a tick update
 * @param {Function} onQuote  - Callback when receiving a quote (bid/ask depth)
 * @returns {{ close: Function, switchSymbol: Function, getWs: Function }}
 *
 * Usage:
 *   const conn = subscribeRealtime("VCB", handleTick, handleQuote);
 *   conn.switchSymbol("HPG");   // switch symbol without reconnect
 *   conn.close();               // cleanup
 */
export function subscribeRealtime(symbol, onTick, onQuote) {
  const url = `${wsBaseUrl()}/ws/stream?symbol=${encodeURIComponent(symbol)}`;
  let ws = null;
  let reconnectTimer = null;
  let intentionalClose = false;

  function connect() {
    ws = new WebSocket(url);

    ws.onopen = () => {
      console.log("[WS] connected:", symbol);
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        switch (msg.type) {
          case "tick":
            if (msg.data && onTick) {
              // Shift UTC timestamp to Vietnam local time
              msg.data.time = (msg.data.time > 1e12 ? Math.floor(msg.data.time / 1000) : msg.data.time) + VN_OFFSET;
              onTick(msg.data);
            }
            break;
          case "quote":
            if (msg.data && onQuote) onQuote(msg.data);
            break;
          case "ping":
            // Reply heartbeat to keep connection alive through nginx proxy
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: "pong" }));
            }
            break;
          default:
            break;
        }
      } catch (_) {}
    };

    ws.onerror = (err) => {
      console.error("[WS] error:", err);
    };

    ws.onclose = () => {
      if (!intentionalClose) {
      // Auto-reconnect after 3s if connection drops unexpectedly
        console.warn("[WS] disconnected, reconnecting in 3s...");
        reconnectTimer = setTimeout(connect, 3000);
      }
    };
  }

  connect();

  return {
    /** Switch tracked symbol without closing/reopening the WS connection */
    switchSymbol(newSymbol) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "subscribe", symbol: newSymbol }));
      }
    },
    /** Get raw WebSocket instance (for debugging) */
    getWs() {
      return ws;
    },
    /** Close connection (call on component unmount) */
    close() {
      intentionalClose = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) {
        ws.close();
        ws = null;
      }
    },
  };
}

// ─── Timeframe definitions ────────────────────────────────────
export const TIMEFRAMES = [
  { key: "1m", label: "1m", seconds: 60 },
  { key: "5m", label: "5m", seconds: 300 },
  { key: "15m", label: "15m", seconds: 900 },
  { key: "30m", label: "30m", seconds: 1800 },
  { key: "1h", label: "1H", seconds: 3600 },
  { key: "4h", label: "4H", seconds: 14400 },
  { key: "1d", label: "1D", seconds: 86400 },
];

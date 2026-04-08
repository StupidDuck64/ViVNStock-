/**
 * PriceBoard.js — Bảng giá chứng khoán kiểu DNSE
 *
 * Displays a real-time stock price board with:
 *   - Symbol, Reference, Ceiling, Floor prices
 *   - 3 Best Bid levels + Matched price/vol + 3 Best Ask levels
 *   - High, Low, Average, +/-, %, Total volume, Foreign buy/sell
 *   - Color coding: Tím (ceiling), Xanh (up), Đỏ (down), Vàng (reference), Xanh dương (floor)
 *   - Auto-refresh every 2 seconds from /api/realtime + /api/realtime/quote + /api/realtime/secdef
 *   - Market filter tabs: VN30, HSX, HNX, UPCOM
 *
 * Data sources:
 *   GET /api/realtime          → all ticks (price, volume)
 *   GET /api/realtime/quote    → bid/ask depth per symbol
 *   GET /api/realtime/secdef   → reference/ceiling/floor
 *   GET /api/symbols           → symbol list
 */

import React, { useEffect, useState, useMemo, useCallback, useRef } from "react";
import { fetchAllRealtime, fetchAllDaily, fetchSymbols } from "../services/api";

/* ─── Top Movers (Gainers/Losers) side panel ─── */
const TIME_FILTERS = [
  { key: "day", label: "Ngày" },
  { key: "month", label: "Tháng" },
  { key: "year", label: "Năm" },
];

function TopMoversPanel({ rows, onSelectSymbol }) {
  const [timeFilter, setTimeFilter] = useState("day");
  const topN = 10;

  // For day filter we use current session changePct
  // Month/year filters would need historical data — for now show intraday data with label
  const sorted = useMemo(() => {
    return [...rows].filter((r) => r.close > 0 && r.ref > 0);
  }, [rows]);

  const gainers = useMemo(() => {
    return [...sorted].sort((a, b) => b.changePct - a.changePct).slice(0, topN);
  }, [sorted, topN]);

  const losers = useMemo(() => {
    return [...sorted].sort((a, b) => a.changePct - b.changePct).slice(0, topN);
  }, [sorted, topN]);

  const fmtPrice = (v) => v ? (v / 1000).toFixed(2) : "—";

  return (
    <div className="w-60 flex-shrink-0 border-l border-bg-tertiary bg-bg-secondary flex flex-col overflow-hidden">
      {/* Time filter */}
      <div className="flex items-center gap-1 px-3 py-2 border-b border-bg-tertiary">
        {TIME_FILTERS.map((tf) => (
          <button
            key={tf.key}
            onClick={() => setTimeFilter(tf.key)}
            className={`px-2 py-1 text-[10px] rounded font-medium transition-colors ${
              timeFilter === tf.key
                ? "bg-blue-600 text-white"
                : "text-text-secondary hover:text-text-primary hover:bg-bg-tertiary"
            }`}
          >
            {tf.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Top Gainers */}
        <div className="px-3 pt-2 pb-1">
          <h3 className="text-[11px] font-semibold text-up mb-1.5 flex items-center gap-1">
            <svg width="10" height="10" viewBox="0 0 10 10"><polygon points="5,1 9,7 1,7" fill="currentColor"/></svg>
            Top tăng
          </h3>
          <div className="space-y-0.5">
            {gainers.map((r, i) => (
              <div
                key={r.sym}
                onClick={() => onSelectSymbol && onSelectSymbol(r.sym)}
                className="flex items-center justify-between px-2 py-1 rounded cursor-pointer hover:bg-bg-tertiary/50 transition-colors"
              >
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-text-secondary w-3 text-right">{i + 1}</span>
                  <span className="text-xs font-semibold text-text-primary">{r.sym}</span>
                </div>
                <div className="text-right">
                  <span className={`text-xs font-mono ${
                    r.changePct >= 6.9 ? "text-purple-400" : "text-up"
                  }`}>+{r.changePct.toFixed(2)}%</span>
                  <span className="text-[10px] text-text-secondary ml-1.5 font-mono">{fmtPrice(r.close)}</span>
                </div>
              </div>
            ))}
            {gainers.length === 0 && <div className="text-[10px] text-text-secondary text-center py-2">Đang tải...</div>}
          </div>
        </div>

        <div className="mx-3 h-px bg-bg-tertiary" />

        {/* Top Losers */}
        <div className="px-3 pt-2 pb-1">
          <h3 className="text-[11px] font-semibold text-down mb-1.5 flex items-center gap-1">
            <svg width="10" height="10" viewBox="0 0 10 10"><polygon points="5,9 9,3 1,3" fill="currentColor"/></svg>
            Top giảm
          </h3>
          <div className="space-y-0.5">
            {losers.map((r, i) => (
              <div
                key={r.sym}
                onClick={() => onSelectSymbol && onSelectSymbol(r.sym)}
                className="flex items-center justify-between px-2 py-1 rounded cursor-pointer hover:bg-bg-tertiary/50 transition-colors"
              >
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-text-secondary w-3 text-right">{i + 1}</span>
                  <span className="text-xs font-semibold text-text-primary">{r.sym}</span>
                </div>
                <div className="text-right">
                  <span className={`text-xs font-mono ${
                    r.changePct <= -6.9 ? "text-blue-400" : "text-down"
                  }`}>{r.changePct.toFixed(2)}%</span>
                  <span className="text-[10px] text-text-secondary ml-1.5 font-mono">{fmtPrice(r.close)}</span>
                </div>
              </div>
            ))}
            {losers.length === 0 && <div className="text-[10px] text-text-secondary text-center py-2">Đang tải...</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

const MARKET_TABS = [
  { key: "VN30", label: "VN30" },
  { key: "HSX", label: "HSX" },
  { key: "HNX", label: "HNX" },
  { key: "UPCOM", label: "UPCOM" },
];

// VN30 basket (April 2026)
const VN30_SYMBOLS = [
  "ACB","BID","BCM","BVH","CTG","FPT","GAS","GVR","HDB","HPG",
  "KDH","LPB","MBB","MSN","MWG","PLX","POW","SAB","SHB","SSB",
  "SSI","STB","TCB","TPB","VCB","VHM","VIB","VIC","VJC","VNM",
];

const API = "/api";

export default function PriceBoard({ onSelectSymbol }) {
  const [symbols, setSymbols] = useState([]);
  const [ticks, setTicks] = useState({});          // symbol → tick
  const [quotes, setQuotes] = useState({});         // symbol → quote
  const [secdefs, setSecdefs] = useState({});       // symbol → secdef
  const [dailyMap, setDailyMap] = useState({});     // symbol → daily (basicPrice, changePct)
  const [activeTab, setActiveTab] = useState("VN30");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState(null);       // { col, dir }
  const intervalRef = useRef(null);

  // Load symbols once
  useEffect(() => {
    fetchSymbols().then((list) => setSymbols(list)).catch(() => {});
  }, []);

  // Batch-fetch all data
  const fetchAll = useCallback(async () => {
    try {
      // Fetch all ticks + daily data in parallel
      const [allTicks, dailyList] = await Promise.all([
        fetchAllRealtime(),
        fetchAllDaily(),
      ]);
      if (Array.isArray(allTicks)) {
        const map = {};
        allTicks.forEach((t) => { if (t?.symbol) map[t.symbol] = t; });
        setTicks(map);
      }
      if (Array.isArray(dailyList)) {
        const dMap = {};
        dailyList.forEach((d) => { if (d?.symbol) dMap[d.symbol] = d; });
        setDailyMap(dMap);
      }

      // Fetch quotes + secdefs in batch for visible symbols
      const visibleSyms = getVisibleSymbols();
      if (visibleSyms.length > 0) {
        // Batch quote/secdef fetch (pipeline via individual requests — could optimize with batch endpoint)
        const quotePromises = visibleSyms.slice(0, 50).map(async (sym) => {
          try {
            const res = await fetch(`${API}/realtime/summary?symbol=${encodeURIComponent(sym)}`);
            if (res.ok) return await res.json();
          } catch (_) {}
          return null;
        });
        const results = await Promise.all(quotePromises);
        const qMap = { ...quotes };
        const sMap = { ...secdefs };
        results.forEach((r) => {
          if (r) {
            if (r.quote) qMap[r.symbol] = r.quote;
            if (r.secdef) sMap[r.symbol] = r.secdef;
          }
        });
        setQuotes(qMap);
        setSecdefs(sMap);
      }
    } catch (e) {
      console.error("PriceBoard fetch error:", e);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, search]);

  // Helper: get visible symbol list
  const getVisibleSymbols = useCallback(() => {
    let syms = [];
    if (activeTab === "VN30") {
      syms = VN30_SYMBOLS;
    } else {
      syms = symbols
        .filter((s) => {
          if (activeTab === "HSX") return s.exchange === "HSX" || s.type === "HSX";
          if (activeTab === "HNX") return s.exchange === "HNX" || s.type === "HNX";
          if (activeTab === "UPCOM") return s.exchange === "UPCOM" || s.type === "UPCOM";
          return true;
        })
        .map((s) => s.symbol);
    }
    if (search.trim()) {
      const q = search.trim().toUpperCase();
      syms = syms.filter((s) => s.includes(q));
    }
    return syms;
  }, [activeTab, symbols, search]);

  // Poll every 2 seconds
  useEffect(() => {
    fetchAll();
    intervalRef.current = setInterval(fetchAll, 2000);
    return () => clearInterval(intervalRef.current);
  }, [fetchAll]);

  // Build rows
  const rows = useMemo(() => {
    const visSyms = getVisibleSymbols();
    return visSyms.map((sym) => {
      const tick = ticks[sym];
      const quote = quotes[sym];
      const secdef = secdefs[sym];

      const daily = dailyMap[sym];
      const close = tick?.close || 0;
      const open = tick?.open || close;
      const high = tick?.high || close;
      const low = tick?.low || close;
      const volume = tick?.volume || 0;
      // Use daily.basicPrice (from producer REST batch) as primary ref — always available
      const ref = daily?.basicPrice || secdef?.basicPrice || daily?.prevClose || open;
      const ceil = secdef?.ceilingPrice || daily?.ceilingPrice || 0;
      const floor = secdef?.floorPrice || daily?.floorPrice || 0;

      const change = close - ref;
      const changePct = (close && ref > 0) ? (change / ref) * 100 : (daily?.changePct ?? 0);

      // 3 best bids
      const bids = [];
      if (quote) {
        if (Array.isArray(quote.bid)) {
          quote.bid.slice(0, 3).forEach((b) => bids.push({ price: b.price, vol: b.quantity || b.volume || 0 }));
        } else {
          for (let i = 1; i <= 3; i++) {
            const k = String(i).padStart(2, "0");
            const p = quote[`bidPrice${k}`] || quote[`bestBidPrice${k}`];
            const v = quote[`bidVolume${k}`] || quote[`bestBidQtty${k}`];
            if (p) bids.push({ price: p, vol: v || 0 });
          }
        }
      }

      // 3 best asks
      const asks = [];
      if (quote) {
        if (Array.isArray(quote.offer)) {
          quote.offer.slice(0, 3).forEach((a) => asks.push({ price: a.price, vol: a.quantity || a.volume || 0 }));
        } else {
          for (let i = 1; i <= 3; i++) {
            const k = String(i).padStart(2, "0");
            const p = quote[`offerPrice${k}`] || quote[`bestOfferPrice${k}`];
            const v = quote[`offerVolume${k}`] || quote[`bestOfferQtty${k}`];
            if (p) asks.push({ price: p, vol: v || 0 });
          }
        }
      }

      return { sym, close, open, high, low, volume, ref, ceil, floor, change, changePct, bids, asks, totalBidVol: quote?.totalBidQtty || 0, totalAskVol: quote?.totalOfferQtty || 0 };
    });
  }, [getVisibleSymbols, ticks, quotes, secdefs, dailyMap]);

  // Sort
  const sortedRows = useMemo(() => {
    if (!sortBy) return rows;
    const { col, dir } = sortBy;
    return [...rows].sort((a, b) => {
      let va = a[col], vb = b[col];
      if (typeof va === "string") return dir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
      return dir === "asc" ? (va || 0) - (vb || 0) : (vb || 0) - (va || 0);
    });
  }, [rows, sortBy]);

  const handleSort = (col) => {
    setSortBy((prev) => {
      if (prev?.col === col) return { col, dir: prev.dir === "asc" ? "desc" : "asc" };
      return { col, dir: "desc" };
    });
  };

  // Format helpers
  const fmtPrice = (v) => v ? (v / 1000).toFixed(2) : "—";
  const fmtVol = (v) => {
    if (!v) return "";
    if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
    if (v >= 1e3) return (v / 1e3).toFixed(0) + "K";
    return String(v);
  };
  const fmtVolFull = (v) => v ? v.toLocaleString("vi-VN") : "";

  // Color logic (DNSE style)
  const priceColor = (price, ref, ceil, floor) => {
    if (!price || !ref) return "text-text-secondary";
    if (ceil && price >= ceil) return "text-purple-400";     // Trần
    if (floor && price <= floor) return "text-blue-400";     // Sàn
    if (price === ref) return "text-yellow-400";              // Tham chiếu
    if (price > ref) return "text-up";                        // Tăng
    return "text-down";                                       // Giảm
  };

  const bgFlash = (price, ref) => {
    if (!price || !ref) return "";
    if (price > ref) return "bg-up/5";
    if (price < ref) return "bg-down/5";
    return "";
  };

  return (
    <div className="flex h-full bg-bg-primary text-text-primary">
      {/* ─── Main table area ─── */}
      <div className="flex flex-col flex-1 min-w-0">
      {/* ─── Header ─── */}
      <div className="flex items-center gap-2 px-4 py-2 bg-bg-secondary border-b border-bg-tertiary">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="🔍 Tìm mã CK"
          className="w-36 bg-bg-tertiary text-text-primary text-xs px-2 py-1.5 rounded outline-none focus:ring-1 focus:ring-blue-500 placeholder:text-text-secondary"
        />
        <div className="flex gap-1">
          {MARKET_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-3 py-1.5 text-xs rounded font-medium transition-colors ${
                activeTab === tab.key
                  ? "bg-blue-600 text-white"
                  : "text-text-secondary hover:text-text-primary hover:bg-bg-tertiary"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <span className="ml-auto text-[10px] text-text-secondary">
          {sortedRows.length} mã · Auto-refresh 2s
        </span>
      </div>

      {/* ─── Table ─── */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-xs border-collapse">
          <thead className="sticky top-0 z-10">
            <tr className="bg-bg-secondary text-text-secondary text-[10px] uppercase tracking-wider">
              <th className="px-2 py-1.5 text-left cursor-pointer hover:text-text-primary border-b border-bg-tertiary" onClick={() => handleSort("sym")}>
                Mã {sortBy?.col === "sym" ? (sortBy.dir === "asc" ? "↑" : "↓") : ""}
              </th>
              <th className="px-1 py-1.5 text-center border-b border-bg-tertiary" colSpan={2}>TC</th>
              <th className="px-1 py-1.5 text-center border-b border-bg-tertiary" colSpan={2}>Trần</th>
              <th className="px-1 py-1.5 text-center border-b border-bg-tertiary" colSpan={2}>Sàn</th>
              <th className="px-1 py-1.5 text-center border-b border-r border-bg-tertiary bg-bg-tertiary/30" colSpan={6}>Bên mua</th>
              <th className="px-1 py-1.5 text-center border-b border-bg-tertiary" colSpan={2}>Khớp lệnh</th>
              <th className="px-1 py-1.5 text-center border-b border-l border-bg-tertiary bg-bg-tertiary/30" colSpan={6}>Bên bán</th>
              <th className="px-1 py-1.5 text-center border-b border-bg-tertiary cursor-pointer hover:text-text-primary" onClick={() => handleSort("changePct")}>
                +/- {sortBy?.col === "changePct" ? (sortBy.dir === "asc" ? "↑" : "↓") : ""}
              </th>
              <th className="px-1 py-1.5 text-center border-b border-bg-tertiary">%</th>
              <th className="px-1 py-1.5 text-center border-b border-bg-tertiary cursor-pointer hover:text-text-primary" onClick={() => handleSort("volume")}>
                Tổng KL {sortBy?.col === "volume" ? (sortBy.dir === "asc" ? "↑" : "↓") : ""}
              </th>
              <th className="px-1 py-1.5 text-center border-b border-bg-tertiary">Cao</th>
              <th className="px-1 py-1.5 text-center border-b border-bg-tertiary">Thấp</th>
            </tr>
            {/* Sub-header for bid/ask columns */}
            <tr className="bg-bg-secondary text-text-secondary text-[10px]">
              <th className="border-b border-bg-tertiary"></th>
              <th className="px-1 border-b border-bg-tertiary">Giá</th>
              <th className="px-1 border-b border-bg-tertiary"></th>
              <th className="px-1 border-b border-bg-tertiary">Giá</th>
              <th className="px-1 border-b border-bg-tertiary"></th>
              <th className="px-1 border-b border-bg-tertiary">Giá</th>
              <th className="px-1 border-b border-bg-tertiary"></th>
              {/* Bid 3 */}
              <th className="px-1 border-b border-r border-bg-tertiary bg-bg-tertiary/20 text-up">Giá 3</th>
              <th className="px-1 border-b border-bg-tertiary bg-bg-tertiary/20 text-up">KL 3</th>
              <th className="px-1 border-b border-bg-tertiary bg-bg-tertiary/20 text-up">Giá 2</th>
              <th className="px-1 border-b border-bg-tertiary bg-bg-tertiary/20 text-up">KL 2</th>
              <th className="px-1 border-b border-bg-tertiary bg-bg-tertiary/20 text-up">Giá 1</th>
              <th className="px-1 border-b border-r border-bg-tertiary bg-bg-tertiary/20 text-up">KL 1</th>
              {/* Matched */}
              <th className="px-1 border-b border-bg-tertiary">Giá</th>
              <th className="px-1 border-b border-bg-tertiary">KL</th>
              {/* Ask 1-3 */}
              <th className="px-1 border-b border-l border-bg-tertiary bg-bg-tertiary/20 text-down">Giá 1</th>
              <th className="px-1 border-b border-bg-tertiary bg-bg-tertiary/20 text-down">KL 1</th>
              <th className="px-1 border-b border-bg-tertiary bg-bg-tertiary/20 text-down">Giá 2</th>
              <th className="px-1 border-b border-bg-tertiary bg-bg-tertiary/20 text-down">KL 2</th>
              <th className="px-1 border-b border-bg-tertiary bg-bg-tertiary/20 text-down">Giá 3</th>
              <th className="px-1 border-b border-r border-bg-tertiary bg-bg-tertiary/20 text-down">KL 3</th>
              <th className="border-b border-bg-tertiary"></th>
              <th className="border-b border-bg-tertiary"></th>
              <th className="border-b border-bg-tertiary"></th>
              <th className="border-b border-bg-tertiary"></th>
              <th className="border-b border-bg-tertiary"></th>
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row) => {
              const pc = priceColor(row.close, row.ref, row.ceil, row.floor);
              const flash = bgFlash(row.close, row.ref);
              return (
                <tr
                  key={row.sym}
                  className={`border-b border-bg-tertiary/50 hover:bg-bg-tertiary/40 cursor-pointer transition-colors ${flash}`}
                  onClick={() => onSelectSymbol && onSelectSymbol(row.sym)}
                >
                  {/* Symbol */}
                  <td className={`px-2 py-1 font-semibold ${pc}`}>{row.sym}</td>
                  {/* TC (Reference) */}
                  <td className="px-1 py-1 text-center text-yellow-400 font-mono">{fmtPrice(row.ref)}</td>
                  <td className="px-0.5"></td>
                  {/* Trần (Ceiling) */}
                  <td className="px-1 py-1 text-center text-purple-400 font-mono">{fmtPrice(row.ceil)}</td>
                  <td className="px-0.5"></td>
                  {/* Sàn (Floor) */}
                  <td className="px-1 py-1 text-center text-blue-400 font-mono">{fmtPrice(row.floor)}</td>
                  <td className="px-0.5"></td>

                  {/* Bid 3 */}
                  <td className="px-1 py-1 text-center text-up font-mono border-l border-bg-tertiary/30">{row.bids[2] ? fmtPrice(row.bids[2].price) : ""}</td>
                  <td className="px-1 py-1 text-center text-text-secondary font-mono">{row.bids[2] ? fmtVol(row.bids[2].vol) : ""}</td>
                  {/* Bid 2 */}
                  <td className="px-1 py-1 text-center text-up font-mono">{row.bids[1] ? fmtPrice(row.bids[1].price) : ""}</td>
                  <td className="px-1 py-1 text-center text-text-secondary font-mono">{row.bids[1] ? fmtVol(row.bids[1].vol) : ""}</td>
                  {/* Bid 1 */}
                  <td className="px-1 py-1 text-center text-up font-mono">{row.bids[0] ? fmtPrice(row.bids[0].price) : ""}</td>
                  <td className="px-1 py-1 text-center text-text-secondary font-mono border-r border-bg-tertiary/30">{row.bids[0] ? fmtVol(row.bids[0].vol) : ""}</td>

                  {/* Matched price + volume */}
                  <td className={`px-1 py-1 text-center font-mono font-bold ${pc}`}>{fmtPrice(row.close)}</td>
                  <td className="px-1 py-1 text-center text-text-primary font-mono">{fmtVol(row.volume)}</td>

                  {/* Ask 1 */}
                  <td className="px-1 py-1 text-center text-down font-mono border-l border-bg-tertiary/30">{row.asks[0] ? fmtPrice(row.asks[0].price) : ""}</td>
                  <td className="px-1 py-1 text-center text-text-secondary font-mono">{row.asks[0] ? fmtVol(row.asks[0].vol) : ""}</td>
                  {/* Ask 2 */}
                  <td className="px-1 py-1 text-center text-down font-mono">{row.asks[1] ? fmtPrice(row.asks[1].price) : ""}</td>
                  <td className="px-1 py-1 text-center text-text-secondary font-mono">{row.asks[1] ? fmtVol(row.asks[1].vol) : ""}</td>
                  {/* Ask 3 */}
                  <td className="px-1 py-1 text-center text-down font-mono">{row.asks[2] ? fmtPrice(row.asks[2].price) : ""}</td>
                  <td className="px-1 py-1 text-center text-text-secondary font-mono border-r border-bg-tertiary/30">{row.asks[2] ? fmtVol(row.asks[2].vol) : ""}</td>

                  {/* Change */}
                  <td className={`px-1 py-1 text-center font-mono ${
                    row.changePct >= 6.9 ? "text-purple-400"
                    : row.changePct <= -6.9 ? "text-blue-400"
                    : row.change > 0 ? "text-up" : row.change < 0 ? "text-down" : "text-yellow-400"
                  }`}>
                    {row.change > 0 ? "+" : ""}{(row.change / 1000).toFixed(2)}
                  </td>
                  {/* Change % */}
                  <td className={`px-1 py-1 text-center font-mono ${
                    row.changePct >= 6.9 ? "text-purple-400"
                    : row.changePct <= -6.9 ? "text-blue-400"
                    : row.changePct > 0 ? "text-up" : row.changePct < 0 ? "text-down" : "text-yellow-400"
                  }`}>
                    {row.changePct > 0 ? "+" : ""}{row.changePct.toFixed(2)}%
                  </td>
                  {/* Total Volume */}
                  <td className="px-1 py-1 text-center text-text-primary font-mono">{fmtVolFull(row.volume)}</td>
                  {/* High */}
                  <td className={`px-1 py-1 text-center font-mono ${priceColor(row.high, row.ref, row.ceil, row.floor)}`}>{fmtPrice(row.high)}</td>
                  {/* Low */}
                  <td className={`px-1 py-1 text-center font-mono ${priceColor(row.low, row.ref, row.ceil, row.floor)}`}>{fmtPrice(row.low)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {sortedRows.length === 0 && (
          <div className="flex items-center justify-center h-40 text-text-secondary text-sm">
            {search ? "Không tìm thấy mã nào" : "Đang tải dữ liệu..."}
          </div>
        )}
      </div>
      </div>

      {/* ─── Right panel: Top Gainers / Losers ─── */}
      <TopMoversPanel rows={rows} onSelectSymbol={onSelectSymbol} />
    </div>
  );
}

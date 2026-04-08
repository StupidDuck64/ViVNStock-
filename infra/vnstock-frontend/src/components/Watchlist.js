/**
 * Watchlist.js — Stock Watchlist (left sidebar)
 *
 * Displays a list of stock symbols with real-time prices.
 * Updates prices every 3s via REST API (GET /api/realtime).
 * Includes search filter and displays % change.
 */

import React, { useEffect, useState, useMemo } from "react";
import { fetchSymbols, fetchAllRealtime, fetchAllDaily } from "../services/api";

export default function Watchlist({ selectedSymbol, onSelect }) {
  const [symbols, setSymbols] = useState([]);
  const [prices, setPrices] = useState({});
  const [dailyMap, setDailyMap] = useState({});
  const [search, setSearch] = useState("");

  // Load symbol list once on mount
  useEffect(() => {
    fetchSymbols()
      .then((list) => setSymbols(list))
      .catch(() => {});
  }, []);

  // Poll realtime prices every 3s + daily data every 30s
  useEffect(() => {
    let active = true;
    const refreshTicks = async () => {
      try {
        const all = await fetchAllRealtime();
        if (!active) return;
        const map = {};
        (all || []).forEach((t) => {
          if (t?.symbol) map[t.symbol] = t;
        });
        setPrices(map);
      } catch (_) {}
    };
    const refreshDaily = async () => {
      try {
        const list = await fetchAllDaily();
        if (!active) return;
        const dMap = {};
        (list || []).forEach((d) => {
          if (d?.symbol) dMap[d.symbol] = d;
        });
        setDailyMap(dMap);
      } catch (_) {}
    };
    refreshTicks();
    refreshDaily();
    const ivTick = setInterval(refreshTicks, 3000);
    const ivDaily = setInterval(refreshDaily, 30000);
    return () => {
      active = false;
      clearInterval(ivTick);
      clearInterval(ivDaily);
    };
  }, []);

  // Filter symbols by search
  const filtered = useMemo(() => {
    if (!search.trim()) return symbols;
    const q = search.trim().toUpperCase();
    return symbols.filter(
      (s) =>
        s.symbol.includes(q) ||
        (s.name && s.name.toUpperCase().includes(q))
    );
  }, [symbols, search]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-3 py-2 border-b border-bg-tertiary">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-1.5">
          Watchlist
        </h3>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search symbol..."
          className="w-full bg-bg-tertiary text-text-primary text-xs px-2 py-1 rounded outline-none focus:ring-1 focus:ring-blue-500 placeholder:text-text-secondary"
        />
      </div>

      {/* Symbol list */}
      <div className="flex-1 overflow-y-auto">
        {filtered.map((s) => {
          const tick = prices[s.symbol];
          const daily = dailyMap[s.symbol];
          // Use live tick price as primary (real-time), fallback to daily for off-hours
          const price = tick?.close || daily?.todayClose || 0;
          // Prefer pre-computed changePct from producer (uses prevClose, same as header)
          // Recalculate only when we have a live tick price AND a valid reference
          const ref = daily?.basicPrice || daily?.prevClose || 0;
          const changePct = (price && ref > 0)
            ? ((price - ref) / ref) * 100
            : (daily?.changePct ?? 0);

          const isUp = changePct >= 0;
          const isActive = selectedSymbol === s.symbol;

          return (
            <button
              key={s.symbol}
              onClick={() => onSelect(s.symbol)}
              className={`w-full flex items-center justify-between px-3 py-2 text-xs transition-colors border-b border-bg-tertiary/50 ${
                isActive
                  ? "bg-blue-600/10 border-l-2 border-l-blue-500"
                  : "hover:bg-bg-tertiary border-l-2 border-l-transparent"
              }`}
            >
              <div className="flex flex-col items-start min-w-0">
                <span className="font-semibold text-text-primary">{s.symbol}</span>
                <span className="text-[10px] text-text-secondary truncate max-w-[80px]">
                  {s.type || s.name || ""}
                </span>
              </div>
              <div className="flex flex-col items-end">
                <span
                  className={`font-mono font-medium ${
                    changePct > 0 ? "text-up" : changePct < 0 ? "text-down" : "text-text-secondary"
                  }`}
                >
                  {price ? price.toLocaleString("vi-VN") : "—"}
                </span>
                {(tick || daily) && (
                  <span
                    className={`text-[10px] font-mono ${
                      changePct > 0 ? "text-up" : changePct < 0 ? "text-down" : "text-text-secondary"
                    }`}
                  >
                    {changePct > 0 ? "+" : ""}
                    {changePct.toFixed(2)}%
                  </span>
                )}
              </div>
            </button>
          );
        })}

        {filtered.length === 0 && (
          <div className="px-3 py-4 text-xs text-text-secondary text-center">
            {search ? "No symbols found" : "Loading..."}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * App.js — VVS Dashboard (main layout)
 * ═══════════════════════════════════════════
 *
 * Two tabs:
 *   1. Biểu đồ (Chart) — TradingView-style with drawing tools + 20+ indicators
 *   2. Bảng giá (Price Board) — DNSE-style real-time price board
 *
 * Layout (Chart tab):
 *   ┌──────────────────────────────────────────────────┐
 *   │  Header: tabs | symbol | price | change | Live   │
 *   ├──┬────────┬───────────────────────┬──────────────┤
 *   │DT│Watchlist│   CandlestickChart   │  Quote Panel │
 *   │  │        │   + ChartOverlay      │  (bid/ask)   │
 *   │  │────────│                       │              │
 *   │  │ News   │                       │  SecDef info │
 *   └──┴────────┴───────────────────────┴──────────────┘
 *   DT = DrawingToolbar (vertical)
 */

import React, { useState, useCallback, useEffect } from "react";
import CandlestickChart from "./components/CandlestickChart";
import Watchlist from "./components/Watchlist";
import NewsTicker from "./components/NewsTicker";
import QuotePanel from "./components/QuotePanel";
import PriceBoard from "./components/PriceBoard";
import SectorHeatmap from "./components/SectorHeatmap";
import DrawingToolbar, { DEFAULT_TOOL_SETTINGS } from "./components/DrawingToolbar";
import { fetchSummary } from "./services/api";

export default function App() {
  const [activeTab, setActiveTab] = useState("chart"); // "chart" | "board" | "sector"
  const [symbol, setSymbol] = useState("VCB");
  const [latestPrice, setLatestPrice] = useState(null);
  const [latestQuote, setLatestQuote] = useState(null);
  const [secdef, setSecdef] = useState(null);   // {basicPrice, ceilingPrice, floorPrice}
  const [daily, setDaily] = useState(null);     // {todayOpen, todayHigh, todayLow, ...}

  // Drawing tools state
  const [activeTool, setActiveTool] = useState("cursor");
  const [drawings, setDrawings] = useState([]);
  const [toolSettings] = useState(DEFAULT_TOOL_SETTINGS);

  const handlePriceUpdate = useCallback((tick) => {
    setLatestPrice(tick);
  }, []);

  const handleQuoteUpdate = useCallback((quote) => {
    setLatestQuote(quote);
  }, []);

  const handleAddDrawing = useCallback((drawing) => {
    setDrawings((prev) => [...prev, drawing]);
  }, []);

  const handleClearDrawings = useCallback(() => {
    setDrawings([]);
    setActiveTool("cursor");
  }, []);

  const handleBoardSelectSymbol = useCallback((sym) => {
    setSymbol(sym);
    setActiveTab("chart");
  }, []);

  // Fetch secdef + daily when symbol changes
  useEffect(() => {
    let cancelled = false;
    fetchSummary(symbol)
      .then((data) => {
        if (cancelled) return;
        if (data.secdef) setSecdef(data.secdef);
        if (data.daily) setDaily(data.daily);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [symbol]);

  // Periodic poll: refresh header price + secdef + daily every 3s as WS fallback.
  // If WebSocket drops silently (nginx timeout, network blip), this ensures
  // the header price never freezes — it always converges to the real-time value.
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const data = await fetchSummary(symbol);
        if (data.tick) handlePriceUpdate(data.tick);
        if (data.secdef) setSecdef(data.secdef);
        if (data.daily) setDaily(data.daily);
      } catch (_) {}
    }, 3000);
    return () => clearInterval(id);
  }, [symbol, handlePriceUpdate]);

  // Calculate % change using basicPrice (tham chiếu) as reference — same logic as SSI iBoard
  const refPrice = secdef?.basicPrice || (latestPrice && latestPrice.open) || 0;
  const change =
    latestPrice && refPrice > 0
      ? ((latestPrice.close - refPrice) / refPrice) * 100
      : null;
  const isUp = latestPrice ? latestPrice.close >= refPrice : true;
  const priceColor = isUp ? "text-up" : "text-down";

  return (
    <div className="h-screen flex flex-col bg-bg-primary text-text-primary overflow-hidden">
      {/* ─── Header ─── */}
      <header className="flex items-center justify-between px-4 py-2 bg-bg-secondary border-b border-bg-tertiary">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-bold tracking-wide">
            <span className="text-blue-400">VVS</span>{" "}
            <span className="text-text-secondary font-normal">Dashboard</span>
          </h1>
          <span className="text-xs text-bg-tertiary">│</span>

          {/* Tab navigation */}
          {[
            { key: "chart", label: "Biểu đồ" },
            { key: "board", label: "Bảng giá" },
            { key: "sector", label: "Nhóm ngành" },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
                activeTab === tab.key
                  ? "bg-blue-600 text-white"
                  : "text-text-secondary hover:text-text-primary hover:bg-bg-tertiary"
              }`}
            >
              {tab.label}
            </button>
          ))}

          {activeTab === "chart" && (
            <>
              <span className="text-xs text-bg-tertiary">│</span>
              <span className="text-sm font-semibold">{symbol}</span>
              {latestPrice && (
                <>
                  <span className={`text-sm font-mono font-bold ${priceColor}`}>
                    {latestPrice.close?.toLocaleString("vi-VN")}
                  </span>
                  {change !== null && (
                    <span className={`text-xs font-mono ${priceColor}`}>
                      {isUp ? "+" : ""}
                      {change.toFixed(2)}%
                    </span>
                  )}
                </>
              )}
              {/* Reference price bar: Trần / Sàn / TC / Mở / Cao / Thấp */}
              {secdef && (
                <>
                  <span className="text-xs text-bg-tertiary">│</span>
                  <span className="text-xs"><span className="text-purple-400">Trần</span> <span className="font-mono text-purple-400">{secdef.ceilingPrice?.toLocaleString("vi-VN")}</span></span>
                  <span className="text-xs"><span className="text-cyan-400">Sàn</span> <span className="font-mono text-cyan-400">{secdef.floorPrice?.toLocaleString("vi-VN")}</span></span>
                  <span className="text-xs"><span className="text-yellow-400">TC</span> <span className="font-mono text-yellow-400">{secdef.basicPrice?.toLocaleString("vi-VN")}</span></span>
                </>
              )}
              {daily && (
                <>
                  <span className="text-xs"><span className="text-text-secondary">Mở</span> <span className="font-mono">{daily.todayOpen?.toLocaleString("vi-VN") || "—"}</span></span>
                  <span className="text-xs"><span className="text-text-secondary">Cao</span> <span className="font-mono">{daily.todayHigh?.toLocaleString("vi-VN") || "—"}</span></span>
                  <span className="text-xs"><span className="text-text-secondary">Thấp</span> <span className="font-mono">{daily.todayLow?.toLocaleString("vi-VN") || "—"}</span></span>
                </>
              )}
            </>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs text-text-secondary">
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            Live
          </span>
          <span>Iceberg · Redis · Trino</span>
        </div>
      </header>

      {/* ─── Chart Tab ─── */}
      {activeTab === "chart" && (
        <div className="flex flex-1 overflow-hidden">
          {/* Drawing toolbar (vertical) */}
          <DrawingToolbar
            activeTool={activeTool}
            onSelectTool={setActiveTool}
            onClearAll={handleClearDrawings}
          />

          {/* Left sidebar: Watchlist + News */}
          <aside className="w-52 flex-shrink-0 bg-bg-secondary border-r border-bg-tertiary flex flex-col">
            <div className="flex-1 overflow-hidden">
              <Watchlist selectedSymbol={symbol} onSelect={setSymbol} />
            </div>
            <div className="border-t border-bg-tertiary">
              <NewsTicker />
            </div>
          </aside>

          {/* Center: Chart + Overlay */}
          <main className="flex-1 relative">
            <CandlestickChart
              symbol={symbol}
              latestPrice={latestPrice}
              onPriceUpdate={handlePriceUpdate}
              onQuoteUpdate={handleQuoteUpdate}
              activeTool={activeTool}
              drawings={drawings}
              onAddDrawing={handleAddDrawing}
              toolSettings={toolSettings}
            />
          </main>

          {/* Right sidebar: Quote Panel */}
          <aside className="w-56 flex-shrink-0 bg-bg-secondary border-l border-bg-tertiary overflow-y-auto">
            <QuotePanel symbol={symbol} quote={latestQuote} />
          </aside>
        </div>
      )}

      {/* ─── Bảng giá Tab ─── */}
      {activeTab === "board" && (
        <div className="flex-1 overflow-hidden">
          <PriceBoard onSelectSymbol={handleBoardSelectSymbol} />
        </div>
      )}

      {/* ─── Nhóm ngành Tab ─── */}
      {activeTab === "sector" && (
        <div className="flex-1 overflow-hidden">
          <SectorHeatmap onSelectSymbol={handleBoardSelectSymbol} />
        </div>
      )}
    </div>
  );
}

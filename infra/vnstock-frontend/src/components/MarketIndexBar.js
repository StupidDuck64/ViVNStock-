/**
 * MarketIndexBar.js — Dải chỉ số thị trường (SSI iBoard style)
 *
 * Hiển thị 4 ô nhỏ cho VNINDEX, VN30, HNX30, HNXINDEX:
 *   - Giá hiện tại, thay đổi (+/-), phần trăm
 *   - Tổng KL, Cao/Thấp
 *   - Sparkline chart intraday (SVG)
 *   - Trạng thái phiên: Đóng cửa / Đang giao dịch
 *
 * Data sources:
 *   GET /api/realtime/summary?symbol=VNINDEX  → tick + daily
 *   GET /api/history?symbol=VNINDEX&interval=1m&limit=300   → sparkline
 *   GET /api/realtime/daily  → batch daily data (for market breadth)
 */

import React, { useEffect, useState, useRef, useCallback } from "react";
import { fetchSummary, fetchAllDaily } from "../services/api";

const INDEX_SYMBOLS = [
  { symbol: "VNINDEX", label: "VNINDEX" },
  { symbol: "VN30",    label: "VN30" },
  { symbol: "HNX30",   label: "HNX30" },
  { symbol: "HNX",     label: "HNXINDEX" },
];

const API = "/api";

// ─── Sparkline (pure SVG) ───────────────────────────────────
function Sparkline({ data, color, width = 200, height = 48 }) {
  if (!data || data.length < 2) return null;

  const closes = data.map((d) => d.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;

  const points = closes
    .map((c, i) => {
      const x = (i / (closes.length - 1)) * width;
      const y = height - ((c - min) / range) * (height - 4) - 2;
      return `${x},${y}`;
    })
    .join(" ");

  // Volume bars (subtle)
  const maxVol = Math.max(...data.map((d) => d.volume || 0)) || 1;
  const barWidth = width / data.length;

  return (
    <svg width={width} height={height} className="block">
      {/* Volume bars */}
      {data.map((d, i) => {
        const bh = ((d.volume || 0) / maxVol) * (height * 0.3);
        return (
          <rect
            key={i}
            x={i * barWidth}
            y={height - bh}
            width={Math.max(barWidth - 0.5, 0.5)}
            height={bh}
            fill={color}
            opacity={0.15}
          />
        );
      })}
      {/* Price line */}
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ─── Single Index Card ───────────────────────────────────────
function IndexCard({ symbol, label, breadth }) {
  const [summary, setSummary] = useState(null);
  const [klines, setKlines] = useState([]);
  const intervalRef = useRef(null);

  const fetchData = useCallback(async () => {
    try {
      const [summaryData, klinesRes] = await Promise.all([
        fetchSummary(symbol),
        fetch(`${API}/history?symbol=${encodeURIComponent(symbol)}&interval=1m&limit=300`)
          .then((r) => (r.ok ? r.json() : []))
          .catch(() => []),
      ]);
      setSummary(summaryData);
      if (Array.isArray(klinesRes) && klinesRes.length > 0) {
        setKlines(klinesRes);
      }
    } catch (_) {}
  }, [symbol]);

  useEffect(() => {
    fetchData();
    intervalRef.current = setInterval(fetchData, 5000);
    return () => clearInterval(intervalRef.current);
  }, [fetchData]);

  // Extract data
  const daily = summary?.daily;
  const tick = summary?.tick;
  const close = daily?.todayClose || tick?.close || 0;
  const open  = daily?.todayOpen  || tick?.open  || close;
  const high  = daily?.todayHigh  || tick?.high  || close;
  const low   = daily?.todayLow   || tick?.low   || close;
  const volume = daily?.todayVol  || tick?.volume || 0;

  // For indexes, basicPrice/prevClose may not exist in daily data.
  // Use daily.prevClose if available; else try secdef.basicPrice;
  // else fallback: the first 1m candle of the day open (approximation of prev close)
  const ref = daily?.basicPrice || daily?.prevClose
    || (klines.length > 0 ? klines[0].open * 1000 : 0)  // history values are /1000
    || open || 0;

  const change = ref > 0 ? close - ref : 0;
  const changePct = daily?.changePct != null
    ? daily.changePct
    : (ref > 0 ? ((close - ref) / ref) * 100 : 0);

  const isUp = changePct >= 0;
  const color = isUp ? "#26a69a" : "#ef5350";

  // Format — index prices are raw points (e.g. 1740.04)
  const fmtIdx = (v) => v ? v.toFixed(2) : "—";
  const fmtChange = (v) => v ? v.toFixed(2) : "0.00";
  const fmtVol = (v) => {
    if (!v) return "—";
    if (v >= 1e9) return (v / 1e9).toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ",") + " Tỷ";
    if (v >= 1e6) return (v / 1e6).toFixed(0) + "M CP";
    if (v >= 1e3) return (v / 1e3).toFixed(0) + "K CP";
    return v.toLocaleString("vi-VN") + " CP";
  };

  // Session status
  const now = new Date();
  const vnHour = (now.getUTCHours() + 7) % 24;
  const isWeekday = now.getDay() > 0 && now.getDay() < 6;
  const isSession = isWeekday && vnHour >= 9 && vnHour < 15;
  const sessionLabel = isSession ? "Đang giao dịch" : "Đóng cửa";

  // Market breadth for this index (from parent)
  const advances = breadth?.advances || 0;
  const declines = breadth?.declines || 0;
  const unchanged = breadth?.unchanged || 0;
  const hasBreadth = advances > 0 || declines > 0;

  return (
    <div className="flex-1 min-w-[240px] bg-bg-secondary rounded border border-bg-tertiary overflow-hidden">
      {/* Top row: Label + High value + Session */}
      <div className="flex items-center justify-between px-3 pt-2 pb-0.5">
        <span className="text-xs font-semibold text-text-primary">{label}</span>
        <span className="text-[10px] text-text-secondary font-mono">{high > 0 ? fmtIdx(high) : ""}</span>
      </div>

      {/* Sparkline */}
      <div className="px-2">
        <Sparkline data={klines} color={color} width={220} height={44} />
      </div>

      {/* Bottom: Price + Change + Stats */}
      <div className="px-3 pb-2 pt-1">
        {/* Price row */}
        <div className="flex items-baseline justify-between">
          <div className="flex items-baseline gap-2">
            <span className="text-base font-bold font-mono" style={{ color }}>
              {close > 0 ? fmtIdx(close) : "—"}
            </span>
            <span className="text-[11px] font-mono" style={{ color }}>
              {close > 0 && ref > 0 ? (
                <>
                  {isUp ? "▲" : "▼"}{Math.abs(changePct).toFixed(2)}%
                </>
              ) : "—"}
            </span>
          </div>
          <span className="text-[10px] text-text-secondary">{sessionLabel}</span>
        </div>

        {/* Stats row */}
        <div className="flex items-center gap-2 mt-0.5 text-[10px]">
          <span className="text-text-secondary font-mono">
            {fmtVol(volume)}
          </span>
          {hasBreadth ? (
            <>
              <span className="text-text-secondary">│</span>
              <span className="text-up">↑{advances}</span>
              <span className="text-down">↓{declines}</span>
              <span className="text-yellow-400">—{unchanged}</span>
            </>
          ) : (
            <>
              <span className="text-text-secondary">│</span>
              <span className="text-text-secondary">C: {fmtIdx(high)}</span>
              <span className="text-text-secondary">T: {fmtIdx(low)}</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Main Bar (4 cards + market breadth) ─────────────────────
export default function MarketIndexBar() {
  const [breadth, setBreadth] = useState({});

  // Compute market breadth from batch daily data (how many stocks up/down/unchanged)
  useEffect(() => {
    async function computeBreadth() {
      try {
        const dailyList = await fetchAllDaily();
        if (!Array.isArray(dailyList)) return;

        // Count advances/declines/unchanged across all stocks
        let advances = 0, declines = 0, unchanged = 0;
        dailyList.forEach((d) => {
          // Skip index symbols themselves
          if (!d.symbol || d.symbol.includes("INDEX") || ["VN30","HNX30","HNX","UPCOM","VN100","VNALL","VNMID","VNSML"].includes(d.symbol)) return;
          const pct = d.changePct;
          if (pct == null) return;
          if (pct > 0.01) advances++;
          else if (pct < -0.01) declines++;
          else unchanged++;
        });

        // Assign breadth to all indices (simplification — same market-wide breadth)
        const b = { advances, declines, unchanged };
        setBreadth({
          VNINDEX: b,
          VN30: b,
          HNX30: b,
          HNX: b,
        });
      } catch (_) {}
    }
    computeBreadth();
    const id = setInterval(computeBreadth, 10000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex gap-2 px-3 py-2 bg-bg-primary border-b border-bg-tertiary overflow-x-auto">
      {INDEX_SYMBOLS.map((idx) => (
        <IndexCard
          key={idx.symbol}
          symbol={idx.symbol}
          label={idx.label}
          breadth={breadth[idx.symbol]}
        />
      ))}
    </div>
  );
}

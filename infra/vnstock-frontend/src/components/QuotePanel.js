/**
 * QuotePanel.js — Bid/Ask Depth Panel
 *
 * Displays the bid/offer order book and SecDef information.
 * Quote data comes from WebSocket ({type:"quote", data}).
 * SecDef data is fetched from REST API when the symbol changes.
 *
 * Layout:
 *   ┌─────────────────────────┐
 *   │  SecDef (Ref/Ceil/Floor) │
 *   ├──────────┬──────────────┤
 *   │  BID     │    Price     │
 *   │  (vol)   │              │
 *   ├──────────┼──────────────┤
 *   │  ASK     │    Price     │
 *   │  (vol)   │              │
 *   └──────────┴──────────────┘
 */

import React, { useEffect, useState } from "react";
import { fetchSummary } from "../services/api";

export default function QuotePanel({ symbol, quote }) {
  const [secdef, setSecdef] = useState(null);

  // Fetch secdef when symbol changes
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await fetchSummary(symbol);
        if (!cancelled && data?.secdef) {
          setSecdef(data.secdef);
        }
      } catch (_) {}
    }
    load();
    return () => { cancelled = true; };
  }, [symbol]);

  const fmtPrice = (v) =>
    v != null ? Number(v).toLocaleString("vi-VN", { maximumFractionDigits: 2 }) : "—";
  const fmtVol = (v) =>
    v != null
      ? v >= 1000
        ? (v / 1000).toFixed(0) + "K"
        : String(v)
      : "";

  // Parse bid/offer arrays from quote data
  // Structure: bid = [{price, volume}, ...], offer = [{price, volume}, ...]
  // Or flattened arrays: bidPrice01..10, bidVolume01..10
  const bids = [];
  const asks = [];

  if (quote) {
    // If quote contains bid/offer arrays
    if (Array.isArray(quote.bid)) {
      quote.bid.forEach((b) => bids.push({ price: b.price, vol: b.volume || b.qty }));
    } else {
      // Fallback: parse bidPrice01..10 format
      for (let i = 1; i <= 10; i++) {
        const key = String(i).padStart(2, "0");
        const p = quote[`bidPrice${key}`] || quote[`bestBidPrice${key}`];
        const v = quote[`bidVolume${key}`] || quote[`bestBidQtty${key}`];
        if (p) bids.push({ price: p, vol: v || 0 });
      }
    }

    if (Array.isArray(quote.offer)) {
      quote.offer.forEach((a) => asks.push({ price: a.price, vol: a.volume || a.qty }));
    } else {
      for (let i = 1; i <= 10; i++) {
        const key = String(i).padStart(2, "0");
        const p = quote[`offerPrice${key}`] || quote[`bestOfferPrice${key}`];
        const v = quote[`offerVolume${key}`] || quote[`bestOfferQtty${key}`];
        if (p) asks.push({ price: p, vol: v || 0 });
      }
    }
  }

  // Max volume for bar width calculation
  const maxVol = Math.max(
    ...bids.map((b) => b.vol || 0),
    ...asks.map((a) => a.vol || 0),
    1
  );

  return (
    <div className="flex flex-col h-full text-xs">
      {/* ─── Header ─── */}
      <div className="px-3 py-2 border-b border-bg-tertiary">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
          Order Book — {symbol}
        </h3>
      </div>

      {/* ─── SecDef info ─── */}
      {secdef && (
        <div className="px-3 py-2 border-b border-bg-tertiary grid grid-cols-3 gap-1 text-center">
          <div>
            <div className="text-text-secondary text-[10px]">Floor</div>
            <div className="text-blue-400 font-mono font-medium">
              {fmtPrice(secdef.floorPrice)}
            </div>
          </div>
          <div>
            <div className="text-text-secondary text-[10px]">TC</div>
            <div className="text-yellow-400 font-mono font-medium">
              {fmtPrice(secdef.basicPrice)}
            </div>
          </div>
          <div>
            <div className="text-text-secondary text-[10px]">Ceiling</div>
            <div className="text-purple-400 font-mono font-medium">
              {fmtPrice(secdef.ceilingPrice)}
            </div>
          </div>
        </div>
      )}

      {/* ─── Bid side (mua) ─── */}
      <div className="px-2 py-1">
        <div className="text-text-secondary text-[10px] uppercase tracking-wider mb-1">
          Bid
        </div>
        {bids.length > 0 ? (
          bids.slice(0, 5).map((b, i) => (
            <div key={`bid-${i}`} className="flex items-center justify-between py-0.5 relative">
              {/* Volume bar background */}
              <div
                className="absolute left-0 top-0 bottom-0 bg-up/10 rounded-sm"
                style={{ width: `${((b.vol || 0) / maxVol) * 100}%` }}
              />
              <span className="relative z-10 text-up font-mono">{fmtPrice(b.price)}</span>
              <span className="relative z-10 text-text-secondary font-mono">{fmtVol(b.vol)}</span>
            </div>
          ))
        ) : (
          <div className="text-text-secondary py-1">—</div>
        )}
      </div>

      {/* ─── Spread ─── */}
      {bids.length > 0 && asks.length > 0 && (
        <div className="px-2 py-1 text-center border-y border-bg-tertiary">
          <span className="text-text-secondary">Spread: </span>
          <span className="font-mono text-text-primary">
            {fmtPrice(asks[0].price - bids[0].price)}
          </span>
        </div>
      )}

      {/* ─── Ask side (bán) ─── */}
      <div className="px-2 py-1">
        <div className="text-text-secondary text-[10px] uppercase tracking-wider mb-1">
          Ask
        </div>
        {asks.length > 0 ? (
          asks.slice(0, 5).map((a, i) => (
            <div key={`ask-${i}`} className="flex items-center justify-between py-0.5 relative">
              <div
                className="absolute left-0 top-0 bottom-0 bg-down/10 rounded-sm"
                style={{ width: `${((a.vol || 0) / maxVol) * 100}%` }}
              />
              <span className="relative z-10 text-down font-mono">{fmtPrice(a.price)}</span>
              <span className="relative z-10 text-text-secondary font-mono">{fmtVol(a.vol)}</span>
            </div>
          ))
        ) : (
          <div className="text-text-secondary py-1">—</div>
        )}
      </div>

      {/* ─── Summary stats ─── */}
      {quote && (
        <div className="mt-auto px-3 py-2 border-t border-bg-tertiary space-y-1">
          {quote.totalBidQtty != null && (
            <div className="flex justify-between">
              <span className="text-text-secondary">Total Bid</span>
              <span className="text-up font-mono">{fmtVol(quote.totalBidQtty)}</span>
            </div>
          )}
          {quote.totalOfferQtty != null && (
            <div className="flex justify-between">
              <span className="text-text-secondary">Total Ask</span>
              <span className="text-down font-mono">{fmtVol(quote.totalOfferQtty)}</span>
            </div>
          )}
        </div>
      )}

      {!quote && !secdef && (
        <div className="flex-1 flex items-center justify-center text-text-secondary">
          Waiting for data...
        </div>
      )}
    </div>
  );
}

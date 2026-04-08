/**
 * SectorHeatmap.js — Dual-panel Sector Heatmap (Tăng | Giảm)
 *
 * Two treemap panels side by side:
 *   LEFT  (green) = Sectors with net positive change, sized by |avgChangePct|
 *   RIGHT (red)   = Sectors with net negative change, sized by |avgChangePct|
 *
 * Within each sector, stocks are sized by |changePct|.
 * Color intensity reflects the magnitude of change.
 *
 * Data source: /api/realtime + /api/realtime/daily
 */

import React, { useEffect, useState, useMemo, useCallback, useRef } from "react";
import { fetchAllRealtime, fetchAllDaily } from "../services/api";

/* ─── Vietnamese market sector definitions ─── */
const SECTOR_MAP = {
  "Ngân hàng": ["VCB", "BID", "CTG", "TCB", "MBB", "ACB", "VPB", "HDB", "STB", "TPB", "SHB", "MSB", "LPB", "EIB", "OCB", "SSB", "ABB", "NAB", "BAB", "BVB", "KLB", "PGB", "VIB", "VBB"],
  "Bất động sản": ["VHM", "VIC", "NVL", "KDH", "DXG", "NLG", "HDG", "PDR", "DIG", "BCG", "CEO", "LDG", "NBB", "SCR", "TDH", "IJC", "HDC", "CII", "KBC", "ITA", "SZC", "AGG", "NTL", "API"],
  "Chứng khoán": ["SSI", "VND", "HCM", "VCI", "SHS", "MBS", "FTS", "CTS", "AGR", "BSI", "DSC", "ORS", "TVS", "BVS", "APS", "EVF"],
  "Thép": ["HPG", "HSG", "NKG", "POM", "TLH", "TVN", "DTL", "SMC", "VGS", "TIS"],
  "Công nghệ": ["FPT", "CMG", "VGI", "FOX", "SAM", "ELC", "ITD", "ONE", "POT", "VTC"],
  "Thực phẩm & Đồ uống": ["VNM", "MSN", "SAB", "KDC", "QNS", "MCH", "SBT", "LSS", "TAC", "ABT", "AAM", "BBC", "BHN", "HAD"],
  "Dầu khí": ["GAS", "PLX", "PVS", "PVD", "BSR", "OIL", "PVB", "PVC", "COM", "PGS", "PVP"],
  "Điện": ["POW", "GEG", "REE", "PC1", "NT2", "HND", "PPC", "SBA", "VSH", "TMP", "CHP", "SHP", "TBC"],
  "Bảo hiểm": ["BVH", "BMI", "BIC", "MIG", "PVI", "PRE", "ABI", "PTI"],
  "Hóa chất & Phân bón": ["DPM", "DCM", "DGC", "CSV", "LAS", "BFC", "NFC", "HVT", "PMB"],
  "Vận tải & Logistics": ["VTP", "GMD", "VOS", "HAH", "MVN", "TMS", "VNA", "SGP", "VNS", "TCL"],
  "Xây dựng": ["CTD", "HBC", "VCG", "ROS", "HUT", "C47", "FCN", "LCG", "CKG", "TV2"],
  "Bán lẻ": ["MWG", "PNJ", "DGW", "FRT", "PET", "AST"],
  "Dệt may": ["TCM", "STK", "TNG", "GMC", "VGT", "MSH", "GIL", "ADS", "EVE"],
  "Cao su & Gỗ": ["GVR", "PHR", "DPR", "TRC", "BRC", "HRC", "SRF", "TNC", "PTB", "TTF"],
  "Thủy sản": ["VHC", "ANV", "IDI", "ACL", "CMX", "FMC", "MPC", "TS4"],
};

/* ─── Squarified Treemap Layout Algorithm ─── */
function squarify(items, x, y, w, h) {
  if (!items.length || w <= 0 || h <= 0) return [];

  const total = items.reduce((s, it) => s + it.weight, 0);
  if (total <= 0) return [];

  const rects = [];
  let remaining = [...items];
  let cx = x, cy = y, cw = w, ch = h;

  while (remaining.length > 0) {
    const isWide = cw >= ch;
    const side = isWide ? ch : cw;
    const totalRemaining = remaining.reduce((s, it) => s + it.weight, 0);

    // Find best row
    let row = [remaining[0]];
    let rowSum = remaining[0].weight;
    let bestRatio = Infinity;

    for (let i = 1; i < remaining.length; i++) {
      const candidate = [...row, remaining[i]];
      const candidateSum = rowSum + remaining[i].weight;
      const rowFraction = candidateSum / totalRemaining;
      const rowSize = rowFraction * (isWide ? cw : ch);

      // Calculate worst aspect ratio in this row
      let worstRatio = 0;
      for (const item of candidate) {
        const itemFraction = item.weight / candidateSum;
        const itemSize = itemFraction * side;
        const ratio = Math.max(rowSize / itemSize, itemSize / rowSize);
        worstRatio = Math.max(worstRatio, ratio);
      }

      if (worstRatio <= bestRatio) {
        bestRatio = worstRatio;
        row = candidate;
        rowSum = candidateSum;
      } else {
        break;
      }
    }

    // Layout this row
    const rowFraction = rowSum / totalRemaining;
    const rowSize = rowFraction * (isWide ? cw : ch);
    let pos = 0;

    for (const item of row) {
      const itemFraction = item.weight / rowSum;
      const itemSize = itemFraction * side;

      if (isWide) {
        rects.push({
          ...item,
          rx: cx,
          ry: cy + pos,
          rw: rowSize,
          rh: itemSize,
        });
        pos += itemSize;
      } else {
        rects.push({
          ...item,
          rx: cx + pos,
          ry: cy,
          rw: itemSize,
          rh: rowSize,
        });
        pos += itemSize;
      }
    }

    // Reduce remaining area
    if (isWide) {
      cx += rowSize;
      cw -= rowSize;
    } else {
      cy += rowSize;
      ch -= rowSize;
    }

    remaining = remaining.slice(row.length);
  }

  return rects;
}

/* ─── Color helpers ─── */
function changePctToColor(pct) {
  if (pct >= 6.9) return "#a855f7"; // ceiling / purple
  if (pct >= 4) return "#16a34a";
  if (pct >= 2) return "#22c55e";
  if (pct >= 0.5) return "#4ade80";
  if (pct > -0.5) return "#6b7280"; // flat / gray
  if (pct > -2) return "#f87171";
  if (pct > -4) return "#ef4444";
  if (pct <= -6.9) return "#3b82f6"; // floor / blue
  return "#dc2626";
}

function changePctToBg(pct) {
  const abs = Math.abs(pct);
  if (pct >= 6.9) return "rgba(168,85,247,0.35)";
  if (pct > 0) {
    const alpha = Math.min(0.12 + abs * 0.06, 0.45);
    return `rgba(34,197,94,${alpha.toFixed(2)})`;
  }
  if (pct <= -6.9) return "rgba(59,130,246,0.35)";
  if (pct < 0) {
    const alpha = Math.min(0.12 + abs * 0.06, 0.45);
    return `rgba(239,68,68,${alpha.toFixed(2)})`;
  }
  return "rgba(107,114,128,0.15)";
}

/* ─── Main Component ─── */
export default function SectorHeatmap({ onSelectSymbol }) {
  const [ticks, setTicks] = useState({});
  const [dailyData, setDailyData] = useState({});
  const [expandedSector, setExpandedSector] = useState(null);
  const containerRef = useRef(null);
  const [dims, setDims] = useState({ w: 800, h: 600 });
  const intervalRef = useRef(null);

  // Fetch tick + daily data
  const fetchData = useCallback(async () => {
    try {
      // Fetch ticks for volume info
      const allTicks = await fetchAllRealtime();
      if (Array.isArray(allTicks)) {
        const map = {};
        allTicks.forEach((t) => { if (t?.symbol) map[t.symbol] = t; });
        setTicks(map);
      }

      // Fetch daily data (has pre-computed changePct from daily candles)
      const dailyList = await fetchAllDaily();
      if (Array.isArray(dailyList)) {
        const dMap = {};
        dailyList.forEach((d) => { if (d?.symbol) dMap[d.symbol] = d; });
        setDailyData(dMap);
      }
    } catch (e) {
      console.error("SectorHeatmap fetch error:", e);
    }
  }, []);

  useEffect(() => {
    fetchData();
    intervalRef.current = setInterval(fetchData, 5000);
    return () => clearInterval(intervalRef.current);
  }, [fetchData]);

  // Measure container
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDims({ w: entry.contentRect.width, h: entry.contentRect.height });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Build sector data
  const sectorData = useMemo(() => {
    const sectors = [];
    for (const [name, syms] of Object.entries(SECTOR_MAP)) {
      const stocks = [];
      let totalChangePct = 0, activeCount = 0, sectorVol = 0;

      for (const sym of syms) {
        const tick = ticks[sym];
        const daily = dailyData[sym];
        const ref = daily?.basicPrice || daily?.prevClose || 0;

        // Use realtime tick price if available, otherwise fall back to daily close
        const liveClose = (tick && tick.close) ? tick.close : (daily?.todayClose || 0);
        if (liveClose && ref > 0) {
          const changePct = ((liveClose - ref) / ref) * 100;
          const vol = daily?.todayVol || tick?.volume || 0;
          stocks.push({ sym, close: liveClose, changePct, volume: vol, ref });
          totalChangePct += changePct;
          sectorVol += vol;
          activeCount++;
        } else if (daily && daily.todayClose) {
          const changePct = daily.changePct || 0;
          const vol = daily.todayVol || 0;
          stocks.push({ sym, close: daily.todayClose, changePct, volume: vol, ref: daily.basicPrice || daily.prevClose });
          totalChangePct += changePct;
          sectorVol += vol;
          activeCount++;
        }
      }

      if (activeCount > 0) {
        const avgChangePct = totalChangePct / activeCount;
        sectors.push({ name, stocks, totalVolume: sectorVol, avgChangePct, activeCount });
      }
    }
    return sectors;
  }, [ticks, dailyData]);

  // Split sectors into gainers and losers — each weighted by |avgChangePct|
  const { gainSectors, lossSectors } = useMemo(() => {
    const gain = [], loss = [];
    for (const s of sectorData) {
      if (s.avgChangePct >= 0) {
        gain.push({ ...s, weight: Math.max(Math.abs(s.avgChangePct), 0.05) });
      } else {
        loss.push({ ...s, weight: Math.max(Math.abs(s.avgChangePct), 0.05) });
      }
    }
    gain.sort((a, b) => b.weight - a.weight);
    loss.sort((a, b) => b.weight - a.weight);
    return { gainSectors: gain, lossSectors: loss };
  }, [sectorData]);

  // Layout for dual panels — proportional width based on total weight
  const { gainRects, lossRects, gainWidth, lossWidth } = useMemo(() => {
    const totalGainWeight = gainSectors.reduce((s, x) => s + x.weight, 0);
    const totalLossWeight = lossSectors.reduce((s, x) => s + x.weight, 0);
    const totalWeight = totalGainWeight + totalLossWeight;

    const available = dims.w - 6;
    let gw, lw;
    if (totalWeight <= 0) { gw = available / 2; lw = available / 2; }
    else if (gainSectors.length === 0) { gw = 0; lw = available; }
    else if (lossSectors.length === 0) { gw = available; lw = 0; }
    else {
      const rawGw = (totalGainWeight / totalWeight) * available;
      gw = Math.max(rawGw, available * 0.2);
      lw = available - gw;
      if (lw < available * 0.2) { lw = available * 0.2; gw = available - lw; }
    }

    const h = dims.h - 4;
    const gr = gainSectors.length > 0 ? squarify(gainSectors, 0, 0, gw, h) : [];
    const lr = lossSectors.length > 0 ? squarify(lossSectors, 0, 0, lw, h) : [];

    return { gainRects: gr, lossRects: lr, gainWidth: gw, lossWidth: lw };
  }, [gainSectors, lossSectors, dims]);

  // Build treemap layout for expanded sector (stocks weighted by |changePct|)
  const stockRects = useMemo(() => {
    if (!expandedSector) return [];
    const sector = sectorData.find((s) => s.name === expandedSector);
    if (!sector) return [];
    const items = sector.stocks
      .sort((a, b) => Math.abs(b.changePct) - Math.abs(a.changePct))
      .map((s) => ({ ...s, weight: Math.max(Math.abs(s.changePct), 0.05) }));
    return squarify(items, 2, 2, dims.w - 4, dims.h - 40);
  }, [expandedSector, sectorData, dims]);

  const fmtVol = (v) => {
    if (v >= 1e9) return (v / 1e9).toFixed(1) + "B";
    if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
    if (v >= 1e3) return (v / 1e3).toFixed(0) + "K";
    return String(v);
  };

  // Compute market-wide summary (proxy VN-Index from sector data)
  const marketSummary = useMemo(() => {
    if (!sectorData.length) return null;
    let totalVol = 0, weightedChange = 0, advances = 0, declines = 0, unchanged = 0;
    sectorData.forEach((s) => {
      s.stocks.forEach((st) => {
        totalVol += st.volume;
        weightedChange += st.changePct * st.volume;
        if (st.changePct > 0.1) advances++;
        else if (st.changePct < -0.1) declines++;
        else unchanged++;
      });
    });
    const avgPct = totalVol > 0 ? weightedChange / totalVol : 0;
    return { avgPct, totalVol, advances, declines, unchanged };
  }, [sectorData]);

  return (
    <div className="flex flex-col h-full bg-bg-primary text-text-primary">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-2 bg-bg-secondary border-b border-bg-tertiary">
        {expandedSector ? (
          <>
            <button
              onClick={() => setExpandedSector(null)}
              className="text-xs text-blue-400 hover:text-blue-300 font-medium"
            >
              ← Tất cả nhóm ngành
            </button>
            <span className="text-xs text-bg-tertiary">│</span>
            <span className="text-sm font-semibold">{expandedSector}</span>
          </>
        ) : (
          <>
            <span className="text-sm font-semibold">Nhóm ngành — Heatmap</span>
            {marketSummary && (
              <>
                <span className="text-xs text-bg-tertiary">│</span>
                <span className={`text-xs font-mono font-bold ${
                  marketSummary.avgPct > 0 ? "text-up" : marketSummary.avgPct < 0 ? "text-down" : "text-text-secondary"
                }`}>
                  VN-Index {marketSummary.avgPct > 0 ? "+" : ""}{marketSummary.avgPct.toFixed(2)}%
                </span>
                <span className="text-[10px] text-text-secondary">
                  <span className="text-up">{marketSummary.advances}↑</span>
                  {" · "}
                  <span className="text-down">{marketSummary.declines}↓</span>
                  {" · "}
                  <span className="text-text-secondary">{marketSummary.unchanged}−</span>
                </span>
              </>
            )}
          </>
        )}
        <span className="ml-auto text-[10px] text-text-secondary">
          {sectorData.length} nhóm · {sectorData.reduce((s, x) => s + x.activeCount, 0)} mã · Auto-refresh 5s
        </span>
      </div>

      {/* Treemap area */}
      <div ref={containerRef} className="flex-1 relative overflow-hidden">
        {!expandedSector ? (
          /* ─── Dual-panel: Gainers (left) | Losers (right) ─── */
          <div className="absolute inset-0 flex">
            {/* Gain panel */}
            {gainSectors.length > 0 && (
              <div className="relative" style={{ width: gainWidth, height: "100%" }}>
                <div className="absolute top-1 left-2 z-20 text-[9px] font-bold text-up/60 uppercase tracking-wider pointer-events-none">
                  Tăng ({gainSectors.length})
                </div>
                {gainRects.map((r) => {
                  const minW = 55, minH = 35;
                  const showLabel = r.rw > minW && r.rh > minH;
                  return (
                    <div
                      key={r.name}
                      onClick={() => setExpandedSector(r.name)}
                      className="absolute border border-bg-tertiary/40 cursor-pointer transition-all hover:brightness-125 hover:z-10 flex flex-col items-center justify-center overflow-hidden"
                      style={{
                        left: r.rx + 2,
                        top: r.ry + 2,
                        width: Math.max(r.rw - 1, 0),
                        height: Math.max(r.rh - 1, 0),
                        backgroundColor: changePctToBg(r.avgChangePct),
                      }}
                    >
                      {showLabel && (
                        <>
                          <span className="text-[11px] font-bold text-text-primary leading-tight text-center px-1 truncate max-w-full">
                            {r.name}
                          </span>
                          <span className="text-xs font-mono font-semibold" style={{ color: changePctToColor(r.avgChangePct) }}>
                            {r.avgChangePct > 0 ? "+" : ""}{r.avgChangePct.toFixed(2)}%
                          </span>
                          {r.rh > 55 && (
                            <span className="text-[9px] text-text-secondary mt-0.5">
                              {r.activeCount} mã · {fmtVol(r.totalVolume)}
                            </span>
                          )}
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Divider */}
            {gainSectors.length > 0 && lossSectors.length > 0 && (
              <div className="w-[2px] bg-bg-tertiary/60 self-stretch flex-shrink-0" />
            )}

            {/* Loss panel */}
            {lossSectors.length > 0 && (
              <div className="relative" style={{ width: lossWidth, height: "100%" }}>
                <div className="absolute top-1 right-2 z-20 text-[9px] font-bold text-down/60 uppercase tracking-wider pointer-events-none">
                  Giảm ({lossSectors.length})
                </div>
                {lossRects.map((r) => {
                  const minW = 55, minH = 35;
                  const showLabel = r.rw > minW && r.rh > minH;
                  return (
                    <div
                      key={r.name}
                      onClick={() => setExpandedSector(r.name)}
                      className="absolute border border-bg-tertiary/40 cursor-pointer transition-all hover:brightness-125 hover:z-10 flex flex-col items-center justify-center overflow-hidden"
                      style={{
                        left: r.rx,
                        top: r.ry + 2,
                        width: Math.max(r.rw - 1, 0),
                        height: Math.max(r.rh - 1, 0),
                        backgroundColor: changePctToBg(r.avgChangePct),
                      }}
                    >
                      {showLabel && (
                        <>
                          <span className="text-[11px] font-bold text-text-primary leading-tight text-center px-1 truncate max-w-full">
                            {r.name}
                          </span>
                          <span className="text-xs font-mono font-semibold" style={{ color: changePctToColor(r.avgChangePct) }}>
                            {r.avgChangePct > 0 ? "+" : ""}{r.avgChangePct.toFixed(2)}%
                          </span>
                          {r.rh > 55 && (
                            <span className="text-[9px] text-text-secondary mt-0.5">
                              {r.activeCount} mã · {fmtVol(r.totalVolume)}
                            </span>
                          )}
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {gainRects.length === 0 && lossRects.length === 0 && (
              <div className="flex items-center justify-center w-full h-full text-text-secondary text-sm">
                Đang tải dữ liệu heatmap...
              </div>
            )}
          </div>
        ) : (
          /* ─── Stock-level treemap (expanded sector) ─── */
          <div className="absolute inset-0" style={{ top: 0 }}>
            {stockRects.map((r) => {
              const showSym = r.rw > 35 && r.rh > 25;
              const showPct = r.rw > 50 && r.rh > 35;
              return (
                <div
                  key={r.sym}
                  onClick={() => onSelectSymbol && onSelectSymbol(r.sym)}
                  className="absolute border border-bg-tertiary/30 cursor-pointer transition-all hover:brightness-125 hover:z-10 flex flex-col items-center justify-center overflow-hidden"
                  style={{
                    left: r.rx,
                    top: r.ry,
                    width: Math.max(r.rw - 1, 0),
                    height: Math.max(r.rh - 1, 0),
                    backgroundColor: changePctToBg(r.changePct),
                  }}
                >
                  {showSym && (
                    <span className="text-xs font-bold text-text-primary leading-tight">{r.sym}</span>
                  )}
                  {showPct && (
                    <span
                      className="text-[10px] font-mono font-semibold"
                      style={{ color: changePctToColor(r.changePct) }}
                    >
                      {r.changePct > 0 ? "+" : ""}{r.changePct.toFixed(2)}%
                    </span>
                  )}
                </div>
              );
            })}
            {stockRects.length === 0 && (
              <div className="flex items-center justify-center h-full text-text-secondary text-sm">
                Không có dữ liệu cho nhóm này
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

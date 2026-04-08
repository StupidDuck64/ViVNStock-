/**
 * CandlestickChart.js — TradingView-style candlestick chart
 *
 * Features:
 *   - 20+ technical indicators (overlay + oscillator)
 *   - Drawing tools (trendline, fib, elliott wave, etc.) via ChartOverlay
 *   - Lazy-loading older candles (infinite scroll)
 *   - WebSocket real-time updates
 *   - SMA/EMA quick toggles + full indicator dropdown
 *
 * Indicators integrate with lightweight-charts via addSeries(LineSeries).
 * Oscillators (RSI, MACD, etc.) rendered in a separate price scale pane.
 */

import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  CrosshairMode,
  LineStyle,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
} from "lightweight-charts";
import { fetchHistory, subscribeRealtime, TIMEFRAMES, fetchSummary } from "../services/api";
import ChartOverlay from "./ChartOverlay";
import IndicatorPanel from "./chart/IndicatorPanel";
import {
  INDICATOR_REGISTRY,
  calcSMA, calcEMA, calcWMA, calcDEMA, calcTEMA, calcVWAP,
  calcBollingerBands, calcEnvelope, calcParabolicSAR, calcIchimoku,
  calcRSI, calcMACD, calcStochastic, calcCCI, calcWilliamsR,
  calcMFI, calcADX, calcOBV, calcATR, calcROC, calcCMF,
} from "./chart/indicatorUtils";

// ─── Theme (TradingView dark) ─────────────────────────────────
const THEME = {
  background: "#131722",
  textColor: "#d1d4dc",
  gridColor: "#1e222d",
  crosshair: "#758696",
  borderColor: "#2a2e39",
  upColor: "#26a69a",
  downColor: "#ef5350",
};

// ─── Indicator calculation dispatcher ─────────────────────────
function computeIndicator(key, candles, period) {
  switch (key) {
    case "sma": return { lines: [calcSMA(candles, period || 20)] };
    case "ema": return { lines: [calcEMA(candles, period || 50)] };
    case "wma": return { lines: [calcWMA(candles, period || 20)] };
    case "dema": return { lines: [calcDEMA(candles, period || 20)] };
    case "tema": return { lines: [calcTEMA(candles, period || 20)] };
    case "vwap": return { lines: [calcVWAP(candles)] };
    case "bb": { const r = calcBollingerBands(candles, period || 20); return { lines: [r.upper, r.middle, r.lower] }; }
    case "envelope": { const r = calcEnvelope(candles, period || 20); return { lines: [r.upper, r.middle, r.lower] }; }
    case "psar": return { lines: [calcParabolicSAR(candles)] };
    case "ichimoku": { const r = calcIchimoku(candles); return { lines: [r.tenkanSen, r.kijunSen, r.senkouA, r.senkouB, r.chikou] }; }
    case "rsi": return { lines: [calcRSI(candles, period || 14)] };
    case "macd": { const r = calcMACD(candles); return { lines: [r.macd, r.signal], histogram: r.histogram }; }
    case "stochastic": { const r = calcStochastic(candles, period || 14); return { lines: [r.k, r.d] }; }
    case "cci": return { lines: [calcCCI(candles, period || 20)] };
    case "williamsR": return { lines: [calcWilliamsR(candles, period || 14)] };
    case "mfi": return { lines: [calcMFI(candles, period || 14)] };
    case "adx": return { lines: [calcADX(candles, period || 14)] };
    case "obv": return { lines: [calcOBV(candles)] };
    case "atr": return { lines: [calcATR(candles, period || 14)] };
    case "roc": return { lines: [calcROC(candles, period || 12)] };
    case "cmf": return { lines: [calcCMF(candles, period || 20)] };
    default: return { lines: [] };
  }
}

export default function CandlestickChart({
  symbol, latestPrice, onPriceUpdate, onQuoteUpdate,
  activeTool, drawings, onAddDrawing, toolSettings,
}) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const candleRef = useRef(null);
  const volumeRef = useRef(null);
  const connRef = useRef(null);
  const candlesRef = useRef([]);
  const prevSymbolRef = useRef(null);
  const liveCandleRef = useRef(null);
  const isLoadingMoreRef = useRef(false);
  const noMoreDataRef = useRef(false);
  const loadOlderDataRef = useRef(null);
  const indicatorSeriesRef = useRef({});   // key → { series: [...LineSeries], histSeries }

  const [timeframe, setTimeframe] = useState("1m");
  const [ohlcv, setOhlcv] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeIndicators, setActiveIndicators] = useState([
    { key: "sma", period: 20 },
    { key: "ema", period: 50 },
  ]);
  const [candlePixels, setCandlePixels] = useState([]);

  // ─── Create chart once ──────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: THEME.background },
        textColor: THEME.textColor,
        fontFamily: "'Inter', sans-serif",
        fontSize: 12,
      },
      grid: {
        vertLines: { color: THEME.gridColor, style: LineStyle.Solid },
        horzLines: { color: THEME.gridColor, style: LineStyle.Solid },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: THEME.crosshair, labelBackgroundColor: "#374151" },
        horzLine: { color: THEME.crosshair, labelBackgroundColor: "#374151" },
      },
      rightPriceScale: {
        borderColor: THEME.borderColor,
        scaleMargins: { top: 0.05, bottom: 0.25 },
        minimumWidth: 80,
      },
      timeScale: {
        borderColor: THEME.borderColor,
        timeVisible: true,
        secondsVisible: false,
        barSpacing: 8,
        minBarSpacing: 3,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
    });

    // Candlestick series
    const cs = chart.addSeries(CandlestickSeries, {
      upColor: THEME.upColor,
      downColor: THEME.downColor,
      borderUpColor: THEME.upColor,
      borderDownColor: THEME.downColor,
      wickUpColor: THEME.upColor,
      wickDownColor: THEME.downColor,
    });

    // Volume histogram (bottom 20% of chart)
    const vs = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleRef.current = cs;
    volumeRef.current = vs;

    // Crosshair → OHLCV overlay
    chart.subscribeCrosshairMove((param) => {
      if (!param.time) {
        setOhlcv(null);
        return;
      }
      const d = param.seriesData?.get(cs);
      const v = param.seriesData?.get(vs);
      if (d) {
        setOhlcv({
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close,
          volume: v?.value,
        });
      }
    });

    // Responsive resize
    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, []);

  // ─── Indicator series management ────────────────────────────
  const updateIndicatorSeries = useCallback((candles) => {
    const chart = chartRef.current;
    if (!chart) return;

    // Remove series for indicators no longer active
    const activeKeys = new Set(activeIndicators.map((a) => a.key));
    Object.keys(indicatorSeriesRef.current).forEach((key) => {
      if (!activeKeys.has(key)) {
        const entry = indicatorSeriesRef.current[key];
        entry.series.forEach((s) => { try { chart.removeSeries(s); } catch (_) {} });
        if (entry.histSeries) { try { chart.removeSeries(entry.histSeries); } catch (_) {} }
        delete indicatorSeriesRef.current[key];
      }
    });

    // Add/update series for active indicators
    activeIndicators.forEach((ai) => {
      const reg = INDICATOR_REGISTRY.find((r) => r.key === ai.key);
      if (!reg) return;

      const result = computeIndicator(ai.key, candles, ai.period);
      const isOsc = reg.type === "oscillator";
      const scaleId = isOsc ? `osc_${ai.key}` : undefined;

      // Color variants for multi-line
      const colorVariants = [reg.color, "#67e8f9", "#a78bfa", "#fbbf24", "#34d399"];

      if (!indicatorSeriesRef.current[ai.key]) {
        // Create new series
        const series = result.lines.map((_, idx) =>
          chart.addSeries(LineSeries, {
            color: colorVariants[idx % colorVariants.length],
            lineWidth: reg.dot ? 0 : 1,
            pointMarkersVisible: reg.dot || false,
            pointMarkersRadius: reg.dot ? 2 : 0,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
            ...(scaleId ? { priceScaleId: scaleId } : {}),
          })
        );

        if (scaleId) {
          chart.priceScale(scaleId).applyOptions({
            scaleMargins: { top: 0.8, bottom: 0.02 },
          });
        }

        let histSeries = null;
        if (result.histogram) {
          histSeries = chart.addSeries(HistogramSeries, {
            priceScaleId: scaleId || "osc_macd",
            priceFormat: { type: "price", precision: 4 },
          });
          if (scaleId) {
            chart.priceScale(scaleId).applyOptions({ scaleMargins: { top: 0.8, bottom: 0.02 } });
          }
        }

        indicatorSeriesRef.current[ai.key] = { series, histSeries };
      }

      // Set data on series
      const entry = indicatorSeriesRef.current[ai.key];
      result.lines.forEach((lineData, idx) => {
        if (entry.series[idx]) {
          entry.series[idx].setData(lineData);
        }
      });
      if (result.histogram && entry.histSeries) {
        entry.histSeries.setData(
          result.histogram.map((h) => ({
            time: h.time,
            value: h.value,
            color: h.value >= 0 ? "rgba(38,166,154,0.6)" : "rgba(239,83,80,0.6)",
          }))
        );
      }
    });
  }, [activeIndicators]);

  // Toggle indicator
  const handleToggleIndicator = useCallback((key) => {
    setActiveIndicators((prev) => {
      const exists = prev.find((a) => a.key === key);
      if (exists) return prev.filter((a) => a.key !== key);
      const reg = INDICATOR_REGISTRY.find((r) => r.key === key);
      return [...prev, { key, period: reg?.defaultPeriod || null }];
    });
  }, []);

  // Update indicator period
  const handleUpdatePeriod = useCallback((key, period) => {
    setActiveIndicators((prev) =>
      prev.map((a) => (a.key === key ? { ...a, period } : a))
    );
  }, []);

  // ─── Load older candles (prepend to chart on scroll-left) ─────
  const loadOlderData = useCallback(async () => {
    if (isLoadingMoreRef.current || noMoreDataRef.current) return;
    const arr = candlesRef.current;
    if (!arr || arr.length === 0) return;

    isLoadingMoreRef.current = true;
    const oldestTime = arr[0].time;
    const endTimeMs = oldestTime > 1e12 ? oldestTime : oldestTime * 1000;

    const CHUNK = { "1m": 2000, "5m": 1500, "15m": 1000, "30m": 800, "1h": 600, "4h": 400 };
    const chunk = CHUNK[timeframe] || 1500;

    try {
      const older = await fetchHistory(symbol, timeframe, chunk, endTimeMs);
      if (!older || older.length === 0) {
        noMoreDataRef.current = true;
        isLoadingMoreRef.current = false;
        return;
      }

      const existingTimes = new Set(arr.map((c) => c.time));
      const uniqueOlder = older.filter((c) => !existingTimes.has(c.time));
      if (uniqueOlder.length === 0) {
        noMoreDataRef.current = true;
        isLoadingMoreRef.current = false;
        return;
      }

      const merged = [...uniqueOlder, ...arr];
      candlesRef.current = merged;

      const ts = chartRef.current?.timeScale();
      const visibleRange = ts?.getVisibleLogicalRange();

      candleRef.current.setData(
        merged.map((c) => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close }))
      );
      volumeRef.current.setData(
        merged.map((c) => ({
          time: c.time,
          value: c.volume,
          color: c.close >= c.open ? "rgba(38,166,154,0.4)" : "rgba(239,83,80,0.4)",
        }))
      );
      updateIndicatorSeries(merged);

      if (visibleRange && ts) {
        const shift = uniqueOlder.length;
        ts.setVisibleLogicalRange({
          from: visibleRange.from + shift,
          to: visibleRange.to + shift,
        });
      }
    } catch (err) {
      console.error("Failed to load older data:", err);
    }
    isLoadingMoreRef.current = false;
  }, [symbol, timeframe, updateIndicatorSeries]);

  // Keep stable ref so the scroll handler never holds a stale closure
  useEffect(() => {
    loadOlderDataRef.current = loadOlderData;
  }, [loadOlderData]);

  // ─── Infinite scroll: load older data when scrolling left ───
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const ts = chart.timeScale();
    const handler = () => {
      if (isLoadingMoreRef.current || noMoreDataRef.current) return;
      const range = ts.getVisibleLogicalRange();
      if (!range) return;
      if (range.from < 20 && loadOlderDataRef.current) {
        loadOlderDataRef.current();
      }
    };

    ts.subscribeVisibleLogicalRangeChange(handler);
    return () => ts.unsubscribeVisibleLogicalRangeChange(handler);
  }, []);

  // ─── Recompute indicators when activeIndicators change ──────
  useEffect(() => {
    const candles = candlesRef.current;
    if (candles && candles.length > 0) {
      updateIndicatorSeries(candles);
    }
  }, [activeIndicators, updateIndicatorSeries]);

  // ─── Hybrid: Load history + subscribe WS ────────────────────
  const loadData = useCallback(async () => {
    if (!candleRef.current) return;
    setLoading(true);
    setError(null);

    const LIMITS = { "1m": 2000, "5m": 2000, "15m": 1500, "30m": 1200, "1h": 1500, "4h": 3000, "1d": 5000 };
    const fetchLimit = LIMITS[timeframe] || 2000;

    try {
      const candles = await fetchHistory(symbol, timeframe, fetchLimit);
      candlesRef.current = candles;
      liveCandleRef.current = null;
      isLoadingMoreRef.current = false;
      noMoreDataRef.current = false;

      candleRef.current.setData(
        candles.map((c) => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close }))
      );
      volumeRef.current.setData(
        candles.map((c) => ({
          time: c.time, value: c.volume,
          color: c.close >= c.open ? "rgba(38,166,154,0.4)" : "rgba(239,83,80,0.4)",
        }))
      );

      // Compute all active indicators
      updateIndicatorSeries(candles);

      if (candles.length > 0) {
        let last = candles[candles.length - 1];
        
        try {
          // Fetch current real-time state to ensure chart accurately reflects final ATC or latest tick
          // Since history candles might lag by a few minutes or miss the final auction match
          const summary = await fetchSummary(symbol);
          const livePrice = summary?.daily?.todayClose || summary?.tick?.close;
          if (livePrice != null && livePrice > 0 && livePrice !== last.close) {
            // Update the last candle's close so the chart displays the correct current real-time price
            last = { ...last, close: livePrice };
            candleRef.current.update(last);
          }
        } catch (e) {
          // Ignore if realtime summary fetch fails, chart will just use last history candle
        }

        if (onPriceUpdate) onPriceUpdate(last);
      }
      chartRef.current?.timeScale().fitContent();
    } catch (err) {
      console.error("Failed to load history:", err);
      setError(err.message || "Failed to load historical data");
    }

    setLoading(false);

    if (connRef.current && prevSymbolRef.current && prevSymbolRef.current !== symbol) {
      connRef.current.switchSymbol(symbol);
      prevSymbolRef.current = symbol;
      return;
    }

    if (!connRef.current) {
      connRef.current = subscribeRealtime(
        symbol,
        (tick) => {
          if (!candleRef.current) return;
          const rawT = tick.time > 1e12 ? Math.floor(tick.time / 1000) : tick.time;
          const tfMeta = TIMEFRAMES.find((tf) => tf.key === timeframe);
          const tfSec = tfMeta ? tfMeta.seconds : 60;
          const t = Math.floor(rawT / tfSec) * tfSec;

          const live = liveCandleRef.current;
          if (live && live.time === t) {
            live.high = Math.max(live.high, tick.high);
            live.low = Math.min(live.low, tick.low);
            live.close = tick.close;
            live.volume = tick.volume || live.volume;
          } else {
            liveCandleRef.current = {
              time: t, open: tick.open, high: tick.high,
              low: tick.low, close: tick.close, volume: tick.volume || 0,
            };
          }

          const candle = liveCandleRef.current;
          candleRef.current.update({
            time: candle.time, open: candle.open,
            high: candle.high, low: candle.low, close: candle.close,
          });
          volumeRef.current.update({
            time: candle.time, value: candle.volume || 0,
            color: candle.close >= candle.open ? "rgba(38,166,154,0.4)" : "rgba(239,83,80,0.4)",
          });

          const arr = candlesRef.current;
          if (arr.length > 0 && arr[arr.length - 1].time === candle.time) {
            arr[arr.length - 1] = { ...candle };
          } else {
            arr.push({ ...candle });
          }

          // Update indicator series for live candle
          updateIndicatorSeries(arr);

          if (onPriceUpdate) onPriceUpdate(tick);
        },
        (quote) => {
          if (onQuoteUpdate) onQuoteUpdate(quote);
        }
      );
      prevSymbolRef.current = symbol;
    }
  }, [symbol, timeframe, onPriceUpdate, onQuoteUpdate, updateIndicatorSeries]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Poll fallback: when latestPrice is updated (via 3s HTTP poll in App.js),
  // patch the chart's last candle so it never lags behind the header price.
  useEffect(() => {
    if (!latestPrice || !candleRef.current || !liveCandleRef.current) return;
    const price = latestPrice.close;
    if (!price || price <= 0) return;
    const live = liveCandleRef.current;
    if (live.close === price) return; // already up-to-date
    live.high = Math.max(live.high, price);
    live.low = Math.min(live.low, price);
    live.close = price;
    candleRef.current.update({
      time: live.time, open: live.open,
      high: live.high, low: live.low, close: live.close,
    });
    const arr = candlesRef.current;
    if (arr.length > 0 && arr[arr.length - 1].time === live.time) {
      arr[arr.length - 1] = { ...live };
    }
    updateIndicatorSeries(arr);
  }, [latestPrice, updateIndicatorSeries]);

  // Cleanup WS on unmount
  useEffect(() => {
    return () => {
      if (connRef.current) {
        connRef.current.close();
        connRef.current = null;
      }
    };
  }, []);

  // When symbol changes, reload history + switch WS
  // When timeframe changes (same symbol), only reload history
  useEffect(() => {
    if (prevSymbolRef.current && prevSymbolRef.current !== symbol && connRef.current) {
      connRef.current.switchSymbol(symbol);
      prevSymbolRef.current = symbol;
    }
  }, [symbol]);

  // ─── Format number (VN locale) ─────────────────────────────
  const fmt = (v) => (v != null ? v.toLocaleString("vi-VN", { maximumFractionDigits: 2 }) : "—");
  const fmtVol = (v) =>
    v != null
      ? v >= 1e6
        ? (v / 1e6).toFixed(1) + "M"
        : v >= 1e3
        ? (v / 1e3).toFixed(1) + "K"
        : v.toLocaleString("vi-VN")
      : "";

  const isUp = ohlcv ? ohlcv.close >= ohlcv.open : true;
  const clr = isUp ? "text-up" : "text-down";

  return (
    <div className="flex flex-col h-full">
      {/* ─── Toolbar: timeframes + indicators ─── */}
      <div className="flex items-center gap-1 px-3 py-1.5 bg-bg-secondary border-b border-bg-tertiary">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf.key}
            onClick={() => setTimeframe(tf.key)}
            className={`px-2.5 py-1 text-xs rounded font-medium transition-colors ${
              timeframe === tf.key
                ? "bg-blue-600 text-white"
                : "text-text-secondary hover:text-text-primary hover:bg-bg-tertiary"
            }`}
          >
            {tf.label}
          </button>
        ))}

        <div className="w-px h-4 bg-bg-tertiary mx-2" />

        {/* Indicator panel dropdown */}
        <IndicatorPanel
          activeIndicators={activeIndicators}
          onToggle={handleToggleIndicator}
          onUpdatePeriod={handleUpdatePeriod}
        />

        {/* Active indicator tags */}
        {activeIndicators.map((ai) => {
          const reg = INDICATOR_REGISTRY.find((r) => r.key === ai.key);
          return (
            <span
              key={ai.key}
              className="px-1.5 py-0.5 text-[10px] rounded font-mono cursor-pointer hover:opacity-70"
              style={{ color: reg?.color, backgroundColor: `${reg?.color}15` }}
              onClick={() => handleToggleIndicator(ai.key)}
              title={`Click to remove ${reg?.name}`}
            >
              {reg?.name}{ai.period ? ` ${ai.period}` : ""} ×
            </span>
          );
        })}

        {loading && (
          <span className="ml-auto text-xs text-text-secondary animate-pulse">
            Loading...
          </span>
        )}
        {error && (
          <span className="ml-auto text-xs text-red-400 truncate max-w-xs" title={error}>
            {error}
          </span>
        )}
      </div>

      {/* ─── OHLCV overlay (crosshair tooltip) ─── */}
      {ohlcv && (
        <div className="absolute top-12 left-4 z-10 flex gap-3 text-xs font-mono bg-bg-primary/80 px-2 py-1 rounded">
          <span className="text-text-secondary">O</span>
          <span className={clr}>{fmt(ohlcv.open)}</span>
          <span className="text-text-secondary">H</span>
          <span className={clr}>{fmt(ohlcv.high)}</span>
          <span className="text-text-secondary">L</span>
          <span className={clr}>{fmt(ohlcv.low)}</span>
          <span className="text-text-secondary">C</span>
          <span className={clr}>{fmt(ohlcv.close)}</span>
          {ohlcv.volume != null && (
            <>
              <span className="text-text-secondary">V</span>
              <span className="text-text-primary">{fmtVol(ohlcv.volume)}</span>
            </>
          )}
        </div>
      )}

      {/* ─── Chart container + Drawing overlay ─── */}
      <div className="flex-1 relative">
        <div ref={containerRef} className="absolute inset-0" />
        <ChartOverlay
          activeTool={activeTool}
          drawings={drawings}
          onAddDrawing={onAddDrawing}
          toolSettings={toolSettings}
          candlePixels={candlePixels}
        />
      </div>
    </div>
  );
}

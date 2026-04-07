/**
 * indicatorUtils.js — 20+ Technical Indicator Calculations
 *
 * All functions accept candles = [{time, open, high, low, close, volume}, ...]
 * and return [{time, value}, ...] (or multi-line for MACD, BB, Ichimoku, etc.)
 */

// ═══════════════════════════════════════════════════════════
// OVERLAY INDICATORS (rendered on main price chart)
// ═══════════════════════════════════════════════════════════

export function calcSMA(candles, period) {
  const out = [];
  for (let i = period - 1; i < candles.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += candles[j].close;
    out.push({ time: candles[i].time, value: +(sum / period).toFixed(4) });
  }
  return out;
}

export function calcEMA(candles, period) {
  if (!candles || candles.length < period) return [];
  const k = 2 / (period + 1);
  const out = [];
  let ema = candles.slice(0, period).reduce((s, c) => s + c.close, 0) / period;
  out.push({ time: candles[period - 1].time, value: +ema.toFixed(4) });
  for (let i = period; i < candles.length; i++) {
    ema = candles[i].close * k + ema * (1 - k);
    out.push({ time: candles[i].time, value: +ema.toFixed(4) });
  }
  return out;
}

export function calcWMA(candles, period) {
  const out = [];
  const denom = (period * (period + 1)) / 2;
  for (let i = period - 1; i < candles.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += candles[i - period + 1 + j].close * (j + 1);
    }
    out.push({ time: candles[i].time, value: +(sum / denom).toFixed(4) });
  }
  return out;
}

export function calcDEMA(candles, period) {
  const ema1 = calcEMA(candles, period);
  if (ema1.length < period) return [];
  const ema2 = calcEMA(ema1.map((e, i) => ({ ...e, close: e.value })), period);
  const map2 = new Map(ema2.map((e) => [e.time, e.value]));
  return ema1
    .filter((e) => map2.has(e.time))
    .map((e) => ({ time: e.time, value: +(2 * e.value - map2.get(e.time)).toFixed(4) }));
}

export function calcTEMA(candles, period) {
  const ema1 = calcEMA(candles, period);
  if (ema1.length < period) return [];
  const ema2 = calcEMA(ema1.map((e) => ({ ...e, close: e.value })), period);
  if (ema2.length < period) return [];
  const ema3 = calcEMA(ema2.map((e) => ({ ...e, close: e.value })), period);
  const map2 = new Map(ema2.map((e) => [e.time, e.value]));
  const map3 = new Map(ema3.map((e) => [e.time, e.value]));
  return ema1
    .filter((e) => map2.has(e.time) && map3.has(e.time))
    .map((e) => ({
      time: e.time,
      value: +(3 * e.value - 3 * map2.get(e.time) + map3.get(e.time)).toFixed(4),
    }));
}

export function calcVWAP(candles) {
  const out = [];
  let cumTPV = 0, cumVol = 0;
  for (let i = 0; i < candles.length; i++) {
    const tp = (candles[i].high + candles[i].low + candles[i].close) / 3;
    cumTPV += tp * (candles[i].volume || 0);
    cumVol += candles[i].volume || 0;
    if (cumVol > 0) {
      out.push({ time: candles[i].time, value: +(cumTPV / cumVol).toFixed(4) });
    }
  }
  return out;
}

export function calcBollingerBands(candles, period = 20, mult = 2) {
  const upper = [], middle = [], lower = [];
  for (let i = period - 1; i < candles.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += candles[j].close;
    const avg = sum / period;
    let sqSum = 0;
    for (let j = i - period + 1; j <= i; j++) sqSum += (candles[j].close - avg) ** 2;
    const std = Math.sqrt(sqSum / period);
    const t = candles[i].time;
    middle.push({ time: t, value: +avg.toFixed(4) });
    upper.push({ time: t, value: +(avg + mult * std).toFixed(4) });
    lower.push({ time: t, value: +(avg - mult * std).toFixed(4) });
  }
  return { upper, middle, lower };
}

export function calcEnvelope(candles, period = 20, pct = 2.5) {
  const sma = calcSMA(candles, period);
  const factor = pct / 100;
  return {
    upper: sma.map((s) => ({ time: s.time, value: +(s.value * (1 + factor)).toFixed(4) })),
    middle: sma,
    lower: sma.map((s) => ({ time: s.time, value: +(s.value * (1 - factor)).toFixed(4) })),
  };
}

export function calcParabolicSAR(candles, step = 0.02, max = 0.2) {
  if (candles.length < 2) return [];
  const out = [];
  let af = step, ep, sar, isLong = true;
  sar = candles[0].low;
  ep = candles[0].high;
  for (let i = 1; i < candles.length; i++) {
    const prev = candles[i - 1];
    const curr = candles[i];
    sar = sar + af * (ep - sar);
    if (isLong) {
      sar = Math.min(sar, prev.low, i > 1 ? candles[i - 2].low : prev.low);
      if (curr.low < sar) {
        isLong = false; sar = ep; ep = curr.low; af = step;
      } else {
        if (curr.high > ep) { ep = curr.high; af = Math.min(af + step, max); }
      }
    } else {
      sar = Math.max(sar, prev.high, i > 1 ? candles[i - 2].high : prev.high);
      if (curr.high > sar) {
        isLong = true; sar = ep; ep = curr.high; af = step;
      } else {
        if (curr.low < ep) { ep = curr.low; af = Math.min(af + step, max); }
      }
    }
    out.push({ time: curr.time, value: +sar.toFixed(4) });
  }
  return out;
}

export function calcIchimoku(candles, tenkan = 9, kijun = 26, senkou = 52) {
  const highest = (arr, start, len) => {
    let h = -Infinity;
    for (let i = start; i > start - len && i >= 0; i--) h = Math.max(h, arr[i].high);
    return h;
  };
  const lowest = (arr, start, len) => {
    let l = Infinity;
    for (let i = start; i > start - len && i >= 0; i--) l = Math.min(l, arr[i].low);
    return l;
  };

  const tenkanSen = [], kijunSen = [], senkouA = [], senkouB = [], chikou = [];
  for (let i = 0; i < candles.length; i++) {
    const t = candles[i].time;
    if (i >= tenkan - 1) {
      tenkanSen.push({ time: t, value: +((highest(candles, i, tenkan) + lowest(candles, i, tenkan)) / 2).toFixed(4) });
    }
    if (i >= kijun - 1) {
      kijunSen.push({ time: t, value: +((highest(candles, i, kijun) + lowest(candles, i, kijun)) / 2).toFixed(4) });
    }
    if (i >= kijun - 1 && i >= tenkan - 1) {
      const tv = (highest(candles, i, tenkan) + lowest(candles, i, tenkan)) / 2;
      const kv = (highest(candles, i, kijun) + lowest(candles, i, kijun)) / 2;
      senkouA.push({ time: t, value: +((tv + kv) / 2).toFixed(4) });
    }
    if (i >= senkou - 1) {
      senkouB.push({ time: t, value: +((highest(candles, i, senkou) + lowest(candles, i, senkou)) / 2).toFixed(4) });
    }
    if (i >= kijun) {
      chikou.push({ time: candles[i - kijun].time, value: +candles[i].close.toFixed(4) });
    }
  }
  return { tenkanSen, kijunSen, senkouA, senkouB, chikou };
}

// ═══════════════════════════════════════════════════════════
// OSCILLATOR INDICATORS (rendered in separate pane below)
// ═══════════════════════════════════════════════════════════

export function calcRSI(candles, period = 14) {
  const out = [];
  if (candles.length < period + 1) return out;
  let gains = 0, losses = 0;
  for (let i = 1; i <= period; i++) {
    const diff = candles[i].close - candles[i - 1].close;
    if (diff > 0) gains += diff; else losses -= diff;
  }
  let avgGain = gains / period, avgLoss = losses / period;
  const rsi = () => (avgLoss === 0 ? 100 : +(100 - 100 / (1 + avgGain / avgLoss)).toFixed(2));
  out.push({ time: candles[period].time, value: rsi() });
  for (let i = period + 1; i < candles.length; i++) {
    const diff = candles[i].close - candles[i - 1].close;
    avgGain = (avgGain * (period - 1) + (diff > 0 ? diff : 0)) / period;
    avgLoss = (avgLoss * (period - 1) + (diff < 0 ? -diff : 0)) / period;
    out.push({ time: candles[i].time, value: rsi() });
  }
  return out;
}

export function calcMACD(candles, fast = 12, slow = 26, signal = 9) {
  const emaFast = calcEMA(candles, fast);
  const emaSlow = calcEMA(candles, slow);
  const fastMap = new Map(emaFast.map((e) => [e.time, e.value]));
  const macdLine = emaSlow
    .filter((e) => fastMap.has(e.time))
    .map((e) => ({ time: e.time, close: fastMap.get(e.time) - e.value, value: +(fastMap.get(e.time) - e.value).toFixed(4) }));
  const signalLine = calcEMA(macdLine, signal).map((e) => ({ time: e.time, value: +e.value.toFixed(4) }));
  const sigMap = new Map(signalLine.map((e) => [e.time, e.value]));
  const histogram = macdLine
    .filter((e) => sigMap.has(e.time))
    .map((e) => ({ time: e.time, value: +(e.value - sigMap.get(e.time)).toFixed(4) }));
  return { macd: macdLine, signal: signalLine, histogram };
}

export function calcStochastic(candles, kPeriod = 14, dPeriod = 3) {
  const kLine = [];
  for (let i = kPeriod - 1; i < candles.length; i++) {
    let hh = -Infinity, ll = Infinity;
    for (let j = i - kPeriod + 1; j <= i; j++) {
      hh = Math.max(hh, candles[j].high);
      ll = Math.min(ll, candles[j].low);
    }
    const k = hh === ll ? 50 : ((candles[i].close - ll) / (hh - ll)) * 100;
    kLine.push({ time: candles[i].time, value: +k.toFixed(2), close: k });
  }
  const dLine = calcSMA(kLine.map((k) => ({ ...k, close: k.value })), dPeriod);
  return { k: kLine.map((k) => ({ time: k.time, value: k.value })), d: dLine };
}

export function calcCCI(candles, period = 20) {
  const out = [];
  for (let i = period - 1; i < candles.length; i++) {
    let sum = 0;
    const tps = [];
    for (let j = i - period + 1; j <= i; j++) {
      const tp = (candles[j].high + candles[j].low + candles[j].close) / 3;
      tps.push(tp);
      sum += tp;
    }
    const avg = sum / period;
    let mad = 0;
    for (const tp of tps) mad += Math.abs(tp - avg);
    mad /= period;
    const cci = mad === 0 ? 0 : (tps[tps.length - 1] - avg) / (0.015 * mad);
    out.push({ time: candles[i].time, value: +cci.toFixed(2) });
  }
  return out;
}

export function calcWilliamsR(candles, period = 14) {
  const out = [];
  for (let i = period - 1; i < candles.length; i++) {
    let hh = -Infinity, ll = Infinity;
    for (let j = i - period + 1; j <= i; j++) {
      hh = Math.max(hh, candles[j].high);
      ll = Math.min(ll, candles[j].low);
    }
    const wr = hh === ll ? -50 : ((hh - candles[i].close) / (hh - ll)) * -100;
    out.push({ time: candles[i].time, value: +wr.toFixed(2) });
  }
  return out;
}

export function calcMFI(candles, period = 14) {
  const out = [];
  const typicals = candles.map((c) => ({
    time: c.time,
    tp: (c.high + c.low + c.close) / 3,
    vol: c.volume || 0,
  }));
  for (let i = period; i < typicals.length; i++) {
    let posFlow = 0, negFlow = 0;
    for (let j = i - period + 1; j <= i; j++) {
      const mf = typicals[j].tp * typicals[j].vol;
      if (typicals[j].tp >= typicals[j - 1].tp) posFlow += mf; else negFlow += mf;
    }
    const ratio = negFlow === 0 ? 100 : 100 - 100 / (1 + posFlow / negFlow);
    out.push({ time: typicals[i].time, value: +ratio.toFixed(2) });
  }
  return out;
}

export function calcADX(candles, period = 14) {
  if (candles.length < period * 2 + 1) return [];
  const tr = [], plusDM = [], minusDM = [];
  for (let i = 1; i < candles.length; i++) {
    const h = candles[i].high, l = candles[i].low, pc = candles[i - 1].close;
    tr.push(Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc)));
    const up = h - candles[i - 1].high, down = candles[i - 1].low - l;
    plusDM.push(up > down && up > 0 ? up : 0);
    minusDM.push(down > up && down > 0 ? down : 0);
  }
  const smooth = (arr) => {
    const out = [arr.slice(0, period).reduce((s, v) => s + v, 0)];
    for (let i = period; i < arr.length; i++) out.push(out[out.length - 1] - out[out.length - 1] / period + arr[i]);
    return out;
  };
  const atr = smooth(tr), sPDM = smooth(plusDM), sMDM = smooth(minusDM);
  const dx = [];
  for (let i = 0; i < atr.length; i++) {
    const pdi = atr[i] === 0 ? 0 : (sPDM[i] / atr[i]) * 100;
    const mdi = atr[i] === 0 ? 0 : (sMDM[i] / atr[i]) * 100;
    const sum = pdi + mdi;
    dx.push(sum === 0 ? 0 : (Math.abs(pdi - mdi) / sum) * 100);
  }
  const out = [];
  if (dx.length >= period) {
    let adx = dx.slice(0, period).reduce((s, v) => s + v, 0) / period;
    out.push({ time: candles[period * 2].time, value: +adx.toFixed(2) });
    for (let i = period; i < dx.length; i++) {
      adx = (adx * (period - 1) + dx[i]) / period;
      if (period * 2 + i - period + 1 < candles.length) {
        out.push({ time: candles[period * 2 + i - period + 1].time, value: +adx.toFixed(2) });
      }
    }
  }
  return out;
}

export function calcOBV(candles) {
  const out = [];
  let obv = 0;
  for (let i = 0; i < candles.length; i++) {
    if (i > 0) {
      if (candles[i].close > candles[i - 1].close) obv += candles[i].volume || 0;
      else if (candles[i].close < candles[i - 1].close) obv -= candles[i].volume || 0;
    }
    out.push({ time: candles[i].time, value: obv });
  }
  return out;
}

export function calcATR(candles, period = 14) {
  if (candles.length < 2) return [];
  const trs = [];
  for (let i = 1; i < candles.length; i++) {
    const h = candles[i].high, l = candles[i].low, pc = candles[i - 1].close;
    trs.push(Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc)));
  }
  const out = [];
  if (trs.length < period) return out;
  let atr = trs.slice(0, period).reduce((s, v) => s + v, 0) / period;
  out.push({ time: candles[period].time, value: +atr.toFixed(4) });
  for (let i = period; i < trs.length; i++) {
    atr = (atr * (period - 1) + trs[i]) / period;
    out.push({ time: candles[i + 1].time, value: +atr.toFixed(4) });
  }
  return out;
}

export function calcROC(candles, period = 12) {
  const out = [];
  for (let i = period; i < candles.length; i++) {
    const prev = candles[i - period].close;
    const roc = prev === 0 ? 0 : ((candles[i].close - prev) / prev) * 100;
    out.push({ time: candles[i].time, value: +roc.toFixed(2) });
  }
  return out;
}

export function calcCMF(candles, period = 20) {
  const out = [];
  for (let i = period - 1; i < candles.length; i++) {
    let mfvSum = 0, volSum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      const hl = candles[j].high - candles[j].low;
      const mfm = hl === 0 ? 0 : ((candles[j].close - candles[j].low) - (candles[j].high - candles[j].close)) / hl;
      mfvSum += mfm * (candles[j].volume || 0);
      volSum += candles[j].volume || 0;
    }
    out.push({ time: candles[i].time, value: +(volSum === 0 ? 0 : mfvSum / volSum).toFixed(4) });
  }
  return out;
}

// ═══════════════════════════════════════════════════════════
// INDICATOR REGISTRY — used by IndicatorPanel to render the list
// ═══════════════════════════════════════════════════════════

export const INDICATOR_REGISTRY = [
  // ─── Overlay (on main chart) ───
  { key: "sma",       name: "SMA",               type: "overlay", defaultPeriod: 20, color: "#e2b714" },
  { key: "ema",       name: "EMA",               type: "overlay", defaultPeriod: 50, color: "#2196f3" },
  { key: "wma",       name: "WMA",               type: "overlay", defaultPeriod: 20, color: "#ff6b6b" },
  { key: "dema",      name: "DEMA",              type: "overlay", defaultPeriod: 20, color: "#a855f7" },
  { key: "tema",      name: "TEMA",              type: "overlay", defaultPeriod: 20, color: "#f97316" },
  { key: "vwap",      name: "VWAP",              type: "overlay", defaultPeriod: null, color: "#22c55e" },
  { key: "bb",        name: "Bollinger Bands",   type: "overlay", defaultPeriod: 20, color: "#e879f9", multiLine: true },
  { key: "envelope",  name: "Envelope",          type: "overlay", defaultPeriod: 20, color: "#67e8f9", multiLine: true },
  { key: "psar",      name: "Parabolic SAR",     type: "overlay", defaultPeriod: null, color: "#fbbf24", dot: true },
  { key: "ichimoku",  name: "Ichimoku Cloud",    type: "overlay", defaultPeriod: null, color: "#ef4444", multiLine: true },
  // ─── Oscillator (separate pane) ───
  { key: "rsi",        name: "RSI",              type: "oscillator", defaultPeriod: 14, color: "#a855f7", range: [0, 100] },
  { key: "macd",       name: "MACD",             type: "oscillator", defaultPeriod: null, color: "#3b82f6", multiLine: true },
  { key: "stochastic", name: "Stochastic",       type: "oscillator", defaultPeriod: 14, color: "#f97316", multiLine: true, range: [0, 100] },
  { key: "cci",        name: "CCI",              type: "oscillator", defaultPeriod: 20, color: "#22c55e" },
  { key: "williamsR",  name: "Williams %R",      type: "oscillator", defaultPeriod: 14, color: "#ef4444", range: [-100, 0] },
  { key: "mfi",        name: "MFI",              type: "oscillator", defaultPeriod: 14, color: "#06b6d4", range: [0, 100] },
  { key: "adx",        name: "ADX",              type: "oscillator", defaultPeriod: 14, color: "#eab308" },
  { key: "obv",        name: "OBV",              type: "oscillator", defaultPeriod: null, color: "#8b5cf6" },
  { key: "atr",        name: "ATR",              type: "oscillator", defaultPeriod: 14, color: "#f43f5e" },
  { key: "roc",        name: "ROC",              type: "oscillator", defaultPeriod: 12, color: "#14b8a6" },
  { key: "cmf",        name: "CMF",              type: "oscillator", defaultPeriod: 20, color: "#fb923c" },
];

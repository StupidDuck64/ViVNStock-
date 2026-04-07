/**
 * IndicatorPanel.js — Dropdown panel listing 20+ indicators with toggles
 *
 * Renders a markdown-style categorized list. Each indicator has:
 *   - Toggle on/off
 *   - Period input (where applicable)
 *   - Color swatch
 */

import React, { useState, useRef, useEffect } from "react";
import { INDICATOR_REGISTRY } from "./indicatorUtils";

export default function IndicatorPanel({ activeIndicators, onToggle, onUpdatePeriod }) {
  const [open, setOpen] = useState(false);
  const panelRef = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) setOpen(false);
    };
    if (open) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const overlays = INDICATOR_REGISTRY.filter((i) => i.type === "overlay");
  const oscillators = INDICATOR_REGISTRY.filter((i) => i.type === "oscillator");

  const isActive = (key) => activeIndicators.some((a) => a.key === key);
  const getPeriod = (key) => {
    const found = activeIndicators.find((a) => a.key === key);
    return found?.period;
  };

  const renderRow = (ind) => {
    const active = isActive(ind.key);
    return (
      <div
        key={ind.key}
        className="flex items-center justify-between py-1 px-2 rounded hover:bg-bg-tertiary group cursor-pointer"
        onClick={() => onToggle(ind.key)}
      >
        <div className="flex items-center gap-2">
          <div
            className={`w-3 h-3 rounded-sm border ${active ? "border-transparent" : "border-gray-500"}`}
            style={{ backgroundColor: active ? ind.color : "transparent" }}
          />
          <span className={`text-xs ${active ? "text-text-primary font-medium" : "text-text-secondary"}`}>
            {ind.name}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {ind.defaultPeriod && active && (
            <input
              type="number"
              className="w-10 bg-bg-primary text-text-primary text-xs text-center rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
              value={getPeriod(ind.key) ?? ind.defaultPeriod}
              onClick={(e) => e.stopPropagation()}
              onChange={(e) => {
                const v = parseInt(e.target.value);
                if (v > 0 && v < 500) onUpdatePeriod(ind.key, v);
              }}
              min={1}
              max={500}
            />
          )}
          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: ind.color }} />
        </div>
      </div>
    );
  };

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={() => setOpen((p) => !p)}
        className={`px-2 py-1 text-xs rounded font-medium transition-colors ${
          open ? "bg-blue-600 text-white" : "text-text-secondary hover:text-text-primary hover:bg-bg-tertiary"
        }`}
        title="Technical Indicators"
      >
        📊 Indicators
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-64 bg-bg-secondary border border-bg-tertiary rounded-lg shadow-xl z-50 max-h-[70vh] overflow-y-auto">
          {/* ─── Overlay section ─── */}
          <div className="px-3 pt-2 pb-1">
            <div className="text-[10px] uppercase tracking-wider text-text-secondary font-semibold border-b border-bg-tertiary pb-1 mb-1">
              📈 Overlay (Main Chart)
            </div>
            {overlays.map(renderRow)}
          </div>

          {/* ─── Oscillator section ─── */}
          <div className="px-3 pt-1 pb-2">
            <div className="text-[10px] uppercase tracking-wider text-text-secondary font-semibold border-b border-bg-tertiary pb-1 mb-1">
              📉 Oscillator (Sub-Panel)
            </div>
            {oscillators.map(renderRow)}
          </div>

          {/* ─── Info ─── */}
          <div className="px-3 py-1.5 border-t border-bg-tertiary">
            <span className="text-[10px] text-text-secondary">
              {activeIndicators.length} / {INDICATOR_REGISTRY.length} active
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

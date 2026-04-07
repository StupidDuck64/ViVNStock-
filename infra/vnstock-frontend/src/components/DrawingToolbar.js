/**
 * DrawingToolbar.js — Vertical toolbar for chart drawing tools (DNSE style)
 */

import React, { useState, useRef, useEffect } from "react";

/* ─── SVG Icon components (16×16 viewBox) ─── */
const SvgIcon = ({ children, ...props }) => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" {...props}>
    {children}
  </svg>
);

const icons = {
  cursor: (
    <SvgIcon>
      <path d="M3 2l4.5 12 1.8-4.2L13.5 8z" fill="currentColor" stroke="none" />
    </SvgIcon>
  ),
  crosshair: (
    <SvgIcon>
      <line x1="8" y1="1" x2="8" y2="15" />
      <line x1="1" y1="8" x2="15" y2="8" />
      <circle cx="8" cy="8" r="3" />
    </SvgIcon>
  ),
  trendline: (
    <SvgIcon>
      <line x1="3" y1="13" x2="13" y2="3" />
      <circle cx="3" cy="13" r="1.2" fill="currentColor" />
      <circle cx="13" cy="3" r="1.2" fill="currentColor" />
    </SvgIcon>
  ),
  horizontal: (
    <SvgIcon>
      <line x1="1" y1="8" x2="15" y2="8" />
      <line x1="1" y1="8" x2="3" y2="6" />
      <line x1="1" y1="8" x2="3" y2="10" />
      <line x1="15" y1="8" x2="13" y2="6" />
      <line x1="15" y1="8" x2="13" y2="10" />
    </SvgIcon>
  ),
  ruler: (
    <SvgIcon>
      <rect x="2" y="5" width="12" height="6" rx="1" />
      <line x1="5" y1="5" x2="5" y2="7.5" />
      <line x1="8" y1="5" x2="8" y2="8" />
      <line x1="11" y1="5" x2="11" y2="7.5" />
    </SvgIcon>
  ),
  rectangle: (
    <SvgIcon>
      <rect x="2" y="3" width="12" height="10" rx="1" />
    </SvgIcon>
  ),
  fibRetracement: (
    <SvgIcon>
      <line x1="2" y1="3" x2="14" y2="3" strokeDasharray="2 1.5" />
      <line x1="2" y1="6" x2="14" y2="6" strokeDasharray="2 1.5" />
      <line x1="2" y1="9" x2="14" y2="9" strokeDasharray="2 1.5" />
      <line x1="2" y1="12" x2="14" y2="12" />
      <path d="M12 3v9" strokeDasharray="1 1" strokeWidth="0.8" />
    </SvgIcon>
  ),
  text: (
    <SvgIcon>
      <line x1="4" y1="3" x2="12" y2="3" />
      <line x1="8" y1="3" x2="8" y2="13" />
      <line x1="5.5" y1="13" x2="10.5" y2="13" />
    </SvgIcon>
  ),
  elliottWave: (
    <SvgIcon>
      <polyline points="1,12 3.5,4 6,9 8.5,2 11,10 13.5,5 15,8" />
    </SvgIcon>
  ),
  harmonicABCD: (
    <SvgIcon>
      <polyline points="2,11 5,3 8,9 13,4" />
      <circle cx="2" cy="11" r="1" fill="currentColor" />
      <circle cx="5" cy="3" r="1" fill="currentColor" />
      <circle cx="8" cy="9" r="1" fill="currentColor" />
      <circle cx="13" cy="4" r="1" fill="currentColor" />
    </SvgIcon>
  ),
  eraser: (
    <SvgIcon>
      <path d="M14 3l-1-1H9L3 8l2.5 2.5M6 11l1 1h4l5-5.5-3-3" />
      <line x1="2" y1="14" x2="14" y2="14" strokeWidth="1" />
    </SvgIcon>
  ),
  magnet: (
    <SvgIcon>
      <path d="M4 3v5a4 4 0 008 0V3" />
      <line x1="4" y1="5" x2="4" y2="3" strokeWidth="2.5" />
      <line x1="12" y1="5" x2="12" y2="3" strokeWidth="2.5" />
    </SvgIcon>
  ),
};

const TOOLS = [
  { key: "cursor",         icon: icons.cursor,         label: "Select / Pan",          group: "basic" },
  { key: "crosshair",      icon: icons.crosshair,      label: "Crosshair",             group: "basic" },
  { key: "trendline",      icon: icons.trendline,      label: "Trend Line",            group: "line" },
  { key: "horizontal",     icon: icons.horizontal,     label: "Horizontal Line",       group: "line" },
  { key: "ruler",          icon: icons.ruler,          label: "Ruler (Distance)",      group: "line" },
  { key: "fibRetracement", icon: icons.fibRetracement, label: "Fibonacci Retracement", group: "fib" },
  { key: "rectangle",      icon: icons.rectangle,      label: "Rectangle",             group: "shape" },
  { key: "text",           icon: icons.text,           label: "Text Annotation",       group: "shape" },
  { key: "elliottWave",    icon: icons.elliottWave,    label: "Elliott Wave",          group: "pattern" },
  { key: "harmonicABCD",   icon: icons.harmonicABCD,   label: "Harmonic ABCD",         group: "pattern" },
  { key: "eraser",         icon: icons.eraser,         label: "Clear All Drawings",    group: "util" },
];

export const DEFAULT_TOOL_SETTINGS = {
  trendline:      { color: "#3b82f6", lineWidth: 2, showLabel: true, dashArray: "solid" },
  horizontal:     { color: "#22c55e", lineWidth: 1.5, showLabel: true, dashArray: "dashed" },
  rectangle:      { color: "#8b5cf6", lineWidth: 1.5, showLabel: false, fillOpacity: 0.1 },
  fibRetracement: { color: "#facc15", lineWidth: 1, showLabel: true, levels: [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1] },
  ruler:          { color: "#facc15", lineWidth: 2, showLabel: true, dashArray: "dashed" },
  elliottWave:    { color: "#f97316", lineWidth: 2, showLabel: true, waveType: "impulse" },
  harmonicABCD:   { color: "#a855f7", lineWidth: 2, showLabel: true, fiboLevels: [0.618, 1.272] },
};

export default function DrawingToolbar({ activeTool, onSelectTool, onClearAll }) {
  const [showSettings, setShowSettings] = useState(null);
  const settingsRef = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (settingsRef.current && !settingsRef.current.contains(e.target)) setShowSettings(null);
    };
    if (showSettings) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showSettings]);

  return (
    <div className="flex flex-col items-center gap-0.5 py-2 px-1.5 bg-bg-secondary border-r border-bg-tertiary w-11">
      {TOOLS.map((tool, idx) => {
        const isActive = activeTool === tool.key;
        const prev = TOOLS[idx - 1];
        const showSep = prev && prev.group !== tool.group;

        return (
          <React.Fragment key={tool.key}>
            {showSep && <div className="w-6 h-px bg-bg-tertiary my-1" />}
            <button
              onClick={() => {
                if (tool.key === "eraser") {
                  onClearAll();
                } else {
                  onSelectTool(tool.key);
                }
              }}
              className={`w-8 h-8 flex items-center justify-center rounded transition-all ${
                isActive
                  ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20"
                  : "text-text-secondary hover:text-text-primary hover:bg-bg-tertiary"
              }`}
              title={tool.label}
            >
              {tool.icon}
            </button>
          </React.Fragment>
        );
      })}
    </div>
  );
}

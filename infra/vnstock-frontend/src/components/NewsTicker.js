/**
 * NewsTicker.js — Market news feed (sidebar bottom)
 *
 * Displays news articles crawled from Redis sorted set.
 * Auto-refreshes every 60 seconds.
 * Shows relative timestamps (3 minutes ago, 2 hours ago).
 */

import React, { useEffect, useState } from "react";
import { fetchNews } from "../services/api";

function timeAgo(ts) {
  if (!ts) return "";
  const now = Date.now() / 1000;
  const sec = ts > 1e12 ? ts / 1000 : ts;
  const diff = Math.max(0, now - sec);

  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function NewsTicker() {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      try {
        const data = await fetchNews(15);
        if (active) setArticles(data);
      } catch (e) {
        console.error("News fetch failed:", e);
      }
      if (active) setLoading(false);
    };
    load();
    const iv = setInterval(load, 60000);
    return () => {
      active = false;
      clearInterval(iv);
    };
  }, []);

  if (!articles.length && !loading) {
    return (
      <div className="p-3 text-xs text-text-secondary">
        No news yet...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-0.5 p-2 overflow-y-auto max-h-64">
      <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider px-1 mb-1">
        Market News
      </h3>
      {loading && articles.length === 0 && (
        <div className="text-xs text-text-secondary px-1 animate-pulse">
          Loading...
        </div>
      )}
      {articles.map((art, i) => (
        <a
          key={art.id || i}
          href={art.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block px-2 py-1.5 rounded text-xs text-text-primary hover:bg-bg-tertiary transition-colors leading-snug group"
        >
          <div className="flex items-start gap-1">
            <span className="text-blue-400 font-medium shrink-0">
              [{art.source || "News"}]
            </span>
            <span className="group-hover:text-blue-300 transition-colors">
              {art.title}
            </span>
          </div>
          {art.published_at && (
            <div className="text-[10px] text-text-secondary mt-0.5 pl-0.5">
              {timeAgo(art.published_at)}
            </div>
          )}
        </a>
      ))}
    </div>
  );
}

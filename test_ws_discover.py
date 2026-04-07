"""Discover DNSE WebSocket endpoints by reverse-engineering their frontend."""
import re
import requests

session = requests.Session()
session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Step 1: Get entradex HTML and find JS bundles
print("=== Step 1: Fetching entradex.dnse.com.vn ===")
r = session.get("https://entradex.dnse.com.vn/", timeout=10)
print(f"Status: {r.status_code}, Length: {len(r.text)}")

# Find JS bundle URLs
js_urls = re.findall(r'src="([^"]*\.js[^"]*)"', r.text)
print(f"JS bundles found: {len(js_urls)}")
for u in js_urls[:20]:
    print(f"  {u}")

# Check for WS references in HTML
ws_refs = re.findall(r'(wss?://[^\s"\'<>]+)', r.text)
if ws_refs:
    print(f"\nWS URLs in HTML:")
    for w in ws_refs:
        print(f"  {w}")

# Step 2: Download JS bundles and search for WS endpoints
print("\n=== Step 2: Scanning JS bundles for WebSocket URLs ===")
base = "https://entradex.dnse.com.vn"
for js_path in js_urls[:15]:
    url = js_path if js_path.startswith("http") else base + js_path
    try:
        jr = session.get(url, timeout=15)
        if jr.status_code != 200:
            continue
        text = jr.text
        # Find WebSocket URLs
        ws_matches = re.findall(r'(wss?://[^\s"\'`,;}\]]+)', text)
        # Find socket/streaming/realtime related config
        config_matches = re.findall(r'["\']([^"\']*(?:socket|stream|realtime|feed|price|ws\b)[^"\']*)["\']', text, re.IGNORECASE)
        if ws_matches or config_matches:
            print(f"\n--- {js_path} ---")
            seen = set()
            for w in ws_matches:
                if w not in seen:
                    print(f"  WS: {w}")
                    seen.add(w)
            for c in config_matches[:20]:
                if c not in seen and len(c) > 3:
                    print(f"  CFG: {c}")
                    seen.add(c)
    except Exception as e:
        print(f"  Error fetching {url}: {e}")

# Step 3: Also check the old Entrade X platform
print("\n=== Step 3: Checking Entrade X / DNSE domains ===")
alt_urls = [
    "https://banggia.dnse.com.vn/",
    "https://banggia.dnse.com.vn/assets/index.js",
    "https://price.dnse.com.vn/",
]
for url in alt_urls:
    try:
        r2 = session.get(url, timeout=10)
        print(f"{url} -> {r2.status_code} ({len(r2.text)} bytes)")
        ws2 = re.findall(r'(wss?://[^\s"\'`,;}\]]+)', r2.text)
        for w in ws2:
            print(f"  WS: {w}")
    except Exception as e:
        print(f"{url} -> Error: {e}")

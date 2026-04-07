"""Extract STOMP WebSocket connection code from DNSE main bundle."""
import re
import requests

session = requests.Session()
session.headers["User-Agent"] = "Mozilla/5.0"

main_url = "https://cdn.dnse.com.vn/dnse-trading/assets/index-Dxh1wRxJ.js"
r = session.get(main_url, timeout=30)
text = r.text

# Find STOMP-related code sections
print("=== STOMP Connection Code ===")
for m in re.finditer(r'(stomP|STOMP|Stomp)', text):
    start = max(0, m.start() - 200)
    end = min(len(text), m.end() + 400)
    snippet = text[start:end]
    # Clean up a bit
    print(f"\n--- offset {m.start()} ---")
    print(snippet)
    print("---")

# Find new WebSocket() calls and surrounding context
print("\n\n=== WebSocket Constructor Code ===")
for m in re.finditer(r'new\s+WebSocket\s*\([^)]+\)', text):
    start = max(0, m.start() - 300)
    end = min(len(text), m.end() + 500)
    snippet = text[start:end]
    print(f"\n--- offset {m.start()} ---")
    print(snippet)
    print("---")

# Find the wss:// dynamic URL construction
print("\n\n=== WSS URL Construction ===")
for m in re.finditer(r'wss://\$\{', text):
    start = max(0, m.start() - 200)
    end = min(len(text), m.end() + 400)
    snippet = text[start:end]
    print(f"\n--- offset {m.start()} ---")
    print(snippet)
    print("---")

# Find connect() calls near STOMP
print("\n\n=== Connect calls ===")
for m in re.finditer(r'\.connect\s*\(', text):
    start = max(0, m.start() - 150)
    end = min(len(text), m.end() + 300)
    snippet = text[start:end]
    # Only print if STOMP/socket/ws related
    if any(kw in snippet.lower() for kw in ['stomp', 'socket', 'ws', 'subscribe', 'datafeed', 'realtime']):
        print(f"\n--- offset {m.start()} ---")
        print(snippet)
        print("---")

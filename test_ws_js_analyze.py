"""Look at the DNSE JS chunks that handle WebSocket connection."""
import re
import requests

session = requests.Session()
session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# The main bundle references lazy chunks like useSocketReconnectCallback, useBondPortfolioRealtime, etc.
# Let's fetch the main JS and find the actual WS connection code
print("=== Fetching main bundle ===")
main_url = "https://cdn.dnse.com.vn/dnse-trading/assets/index-Dxh1wRxJ.js"
r = session.get(main_url, timeout=30)
text = r.text

# Search for WebSocket constructor patterns
ws_patterns = [
    r'new\s+WebSocket\s*\([^)]+\)',
    r'WebSocket\s*\(\s*[`"\'](.*?)[`"\']\s*\)',
    r'\.connect\s*\([^)]*wss?[^)]*\)',
    r'socket\.connect',
    r'createConnection.*wss',
    r'STOMP',
    r'stomp',
    r'SockJS',
    r'sockjs',
    r'protobuf',
    r'protobuff',
    r'\.proto\b',
    r'MessagePack',
    r'msgpack',
    r'avro',
    r'grpc',
    r'gRPC',
]

print("\n=== Pattern matches in main bundle ===")
for pat in ws_patterns:
    matches = re.findall(pat, text, re.IGNORECASE)
    if matches:
        print(f"Pattern '{pat}': {len(matches)} matches")
        for m in matches[:3]:
            if isinstance(m, str) and len(m) > 200:
                m = m[:200]
            print(f"  {m}")

# Search for the chunk files that handle socket
print("\n=== Looking for socket-related chunk files ===")
chunk_refs = re.findall(r'"(assets/[^"]*(?:[Ss]ocket|[Rr]ealtime|[Dd]atafeed|[Pp]rice|[Ss]tream)[^"]*\.js)"', text)
print(f"Socket-related chunks: {chunk_refs}")

# Also look for chunk loading patterns with socket keywords
chunk_patterns = re.findall(r'"([\w-]+)":\(\)=>[\w]+\("(assets/[^"]+\.js)"\)', text)
socket_chunks = [(name, path) for name, path in chunk_patterns if any(kw in name.lower() for kw in ['socket', 'realtime', 'price', 'feed', 'stream', 'ws'])]
print(f"Named socket chunks: {socket_chunks}")

# Get the useSocketReconnectCallback chunk
for name in ['useSocketReconnectCallback-BVzSldFg', 'useListMarketPrice-Dc8FR9Hv', 'useBondPortfolioRealtime-1wGiypf6']:
    chunk_url = f"https://cdn.dnse.com.vn/dnse-trading/assets/{name}.js"
    try:
        cr = session.get(chunk_url, timeout=10)
        if cr.status_code == 200:
            ctext = cr.text
            print(f"\n=== Chunk: {name}.js ({len(ctext)} bytes) ===")
            # Find WS-related code
            for pat in [r'new\s+WebSocket', r'\.connect\(', r'wss://', r'ws://', r'subscribe', r'STOMP', r'protobuf', r'\.send\(', r'onmessage', r'onopen']:
                m = re.findall(pat, ctext, re.IGNORECASE)
                if m:
                    print(f"  Pattern '{pat}': {len(m)} matches")
            # Get surrounding context of WS-related code
            for ws_match in re.finditer(r'(new\s+WebSocket|\.connect\(|wss://|protobuf)', ctext, re.IGNORECASE):
                start = max(0, ws_match.start() - 100)
                end = min(len(ctext), ws_match.end() + 300)
                snippet = ctext[start:end].replace('\n', ' ')
                print(f"  Context: ...{snippet}...")
    except Exception as e:
        print(f"  Error: {e}")

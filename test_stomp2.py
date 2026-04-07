"""Test DNSE WS with Sec-WebSocket-Protocol and gRPC-web headers."""
import websocket
import ssl
import time

API_KEY = "eyJvcmciOiJkbnNlIiwiaWQiOiI3M2JlOGU3MzFhZWQ0MTFkODA5ODYxZDRiN2IxZWM4YSIsImgiOiJtdXJtdXIxMjgifQ=="

BASE_URLS = [
    "wss://datafeed-krx.dnse.com.vn/wss",
    "wss://realtime-krx.dnse.com.vn/wss",
]

# Different subprotocol options
SUBPROTOCOLS = [
    ["v12.stomp", "v11.stomp", "v10.stomp"],
    ["v12.stomp"],
    ["stomp"],
    ["grpc-websockets"],
    None,  # plain WS with just custom Sec-WebSocket-Version
]

STOMP_CONNECT = "CONNECT\naccept-version:1.2\nheart-beat:10000,10000\n\n\x00"

for url in BASE_URLS:
    for sp in SUBPROTOCOLS:
        tag = f"{url} subprotocol={sp}"
        try:
            ws = websocket.create_connection(
                url,
                header=[
                    f"Authorization: Bearer {API_KEY}",
                    "Origin: https://entradex.dnse.com.vn",
                    "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                ],
                subprotocols=sp,
                timeout=8,
                sslopt={"cert_reqs": ssl.CERT_NONE},
            )
            print(f"[CONNECTED] {tag}")
            ws.send(STOMP_CONNECT)
            time.sleep(2)
            try:
                resp = ws.recv()
                print(f"  [RECV] {repr(resp[:400])}")
            except:
                print(f"  [NO RESPONSE]")
            ws.close()
        except Exception as e:
            err = str(e)[:120]
            print(f"[FAIL] {tag} -> {err}")
    print()

# Also try the DNSE developers API endpoint for WS docs
print("=== Checking developers.dnse.com.vn for WS docs ===")
import requests
try:
    r = requests.get("https://developers.dnse.com.vn", timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    print(f"Status: {r.status_code}")
    # Check for websocket mentions
    text = r.text.lower()
    for kw in ["websocket", "stomp", "realtime", "datafeed", "socket"]:
        if kw in text:
            idx = text.index(kw)
            print(f"  Found '{kw}' at pos {idx}: ...{r.text[max(0,idx-30):idx+80]}...")
except Exception as e:
    print(f"  Error: {e}")

# Try the datafeeds API
print("\n=== Checking api.dnse.com.vn/datafeeds ===")
try:
    r = requests.get("https://api.dnse.com.vn/datafeeds", timeout=10, 
                      headers={"Authorization": f"Bearer {API_KEY}", "User-Agent": "Mozilla/5.0"})
    print(f"Status: {r.status_code} Body: {r.text[:500]}")
except Exception as e:
    print(f"  Error: {e}")

# Try gRPC endpoint
print("\n=== Checking gRPC endpoints ===")  
for url in ["wss://datafeed-krx.dnse.com.vn/grpc", "wss://datafeed-krx.dnse.com.vn/api"]:
    try:
        ws = websocket.create_connection(
            url,
            header=["Origin: https://entradex.dnse.com.vn", f"Authorization: Bearer {API_KEY}"],
            timeout=8,
            sslopt={"cert_reqs": ssl.CERT_NONE},
        )
        print(f"[CONNECTED] {url}")
        ws.close()
    except Exception as e:
        print(f"[FAIL] {url} -> {str(e)[:100]}")

"""Test DNSE STOMP WebSocket connection with all known endpoints."""
import websocket
import time
import ssl
import json

API_KEY = "eyJvcmciOiJkbnNlIiwiaWQiOiI3M2JlOGU3MzFhZWQ0MTFkODA5ODYxZDRiN2IxZWM4YSIsImgiOiJtdXJtdXIxMjgifQ=="

ENDPOINTS = [
    "wss://datafeed-krx.dnse.com.vn/wss",
    "wss://realtime-krx.dnse.com.vn/wss",
    "wss://datafeed-krx.dnse.com.vn/websocket",
    "wss://realtime-krx.dnse.com.vn/websocket",
    "wss://datafeed-krx.dnse.com.vn/ws",
    "wss://realtime-krx.dnse.com.vn/ws",
]

HEADERS_OPTIONS = [
    {
        "Origin": "https://entradex.dnse.com.vn",
        "Authorization": f"Bearer {API_KEY}",
    },
    {
        "Origin": "https://trading.dnse.com.vn",
        "Authorization": f"Bearer {API_KEY}",
    },
    {
        "Origin": "https://entradex.dnse.com.vn",
    },
]

STOMP_CONNECT = "CONNECT\naccept-version:1.2\nheart-beat:10000,10000\n\n\x00"
STOMP_CONNECT_AUTH = f"CONNECT\naccept-version:1.2\nheart-beat:10000,10000\nAuthorization:Bearer {API_KEY}\n\n\x00"

def test_endpoint(url, headers, use_auth_in_stomp=False):
    tag = f"{url} | origin={headers.get('Origin','none')[:30]} | auth_stomp={use_auth_in_stomp}"
    try:
        ws = websocket.create_connection(
            url,
            header=[f"{k}: {v}" for k, v in headers.items()],
            timeout=8,
            sslopt={"cert_reqs": ssl.CERT_NONE},
        )
        print(f"  [CONNECTED] {tag}")

        # Send STOMP CONNECT frame
        frame = STOMP_CONNECT_AUTH if use_auth_in_stomp else STOMP_CONNECT
        ws.send(frame)
        print(f"  [SENT STOMP CONNECT]")

        # Wait for response
        time.sleep(2)
        try:
            resp = ws.recv()
            print(f"  [RECV] {repr(resp[:300])}")

            # If STOMP CONNECTED, try subscribing
            if "CONNECTED" in resp:
                print(f"  *** STOMP CONNECTED! ***")
                # Subscribe to a stock
                sub = "SUBSCRIBE\nid:sub-0\ndestination:/topic/stock/VCB\n\n\x00"
                ws.send(sub)
                time.sleep(3)
                try:
                    data = ws.recv()
                    print(f"  [DATA] {repr(data[:500])}")
                except:
                    print(f"  [NO DATA after subscribe]")
        except websocket.WebSocketTimeoutException:
            print(f"  [TIMEOUT waiting for STOMP response]")
        except Exception as e:
            print(f"  [RECV ERROR] {e}")
        ws.close()
    except Exception as e:
        err = str(e)[:100]
        print(f"  [FAIL] {tag} -> {err}")

print("=" * 80)
print("Testing DNSE STOMP WebSocket endpoints")
print("=" * 80)

for url in ENDPOINTS:
    for hdrs in HEADERS_OPTIONS:
        for auth_stomp in [False, True]:
            test_endpoint(url, hdrs, auth_stomp)
    print()

# Also try with token in query string
print("\n=== Token as query param ===")
for url in ENDPOINTS[:2]:
    qurl = f"{url}?token={API_KEY}"
    test_endpoint(qurl, {"Origin": "https://entradex.dnse.com.vn"}, False)
    test_endpoint(qurl, {"Origin": "https://entradex.dnse.com.vn"}, True)

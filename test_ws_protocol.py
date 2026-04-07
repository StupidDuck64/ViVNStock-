"""Probe DNSE WS endpoints to discover protocol."""
import requests
import websocket
import ssl
import json

# Probe via HTTP first
urls = [
    'https://datafeed-krx.dnse.com.vn/wss',
    'https://datafeed-krx.dnse.com.vn/wss/info',
    'https://datafeed-krx.dnse.com.vn/info',
    'https://datafeed-krx.dnse.com.vn/',
    'https://realtime-krx.dnse.com.vn/wss',
    'https://realtime-krx.dnse.com.vn/wss/info',
    'https://realtime-krx.dnse.com.vn/info',
    'https://realtime-krx.dnse.com.vn/',
    'https://api.dnse.com.vn/datafeeds',
    'https://api.dnse.com.vn/datafeeds/info',
]
print("=== HTTP Probe ===")
for url in urls:
    try:
        r = requests.get(url, timeout=5, headers={'Origin': 'https://entradex.dnse.com.vn'}, verify=False)
        body = r.text[:300].replace('\n', ' ')
        print(f'{r.status_code} {url}')
        print(f'  Headers: {dict(list(r.headers.items())[:5])}')
        print(f'  Body: {body}')
    except Exception as e:
        print(f'ERR {url} -> {e}')
    print()

# Test with Sec-WebSocket-Protocol header (STOMP)
print("\n=== WebSocket with Sub-Protocol ===")
API_KEY = 'eyJvcmciOiJkbnNlIiwiaWQiOiI3M2JlOGU3MzFhZWQ0MTFkODA5ODYxZDRiN2IxZWM4YSIsImgiOiJtdXJtdXIxMjgifQ=='
ORIGIN = 'https://entradex.dnse.com.vn'

ws_tests = [
    # (url, subprotocols)
    ('wss://datafeed-krx.dnse.com.vn/wss', ['v10.stomp', 'v11.stomp', 'v12.stomp']),
    ('wss://datafeed-krx.dnse.com.vn/wss', ['stomp']),
    ('wss://datafeed-krx.dnse.com.vn/wss', ['graphql-ws']),
    ('wss://datafeed-krx.dnse.com.vn/wss', None),
    ('wss://realtime-krx.dnse.com.vn/wss', ['v10.stomp', 'v11.stomp', 'v12.stomp']),
    ('wss://realtime-krx.dnse.com.vn/wss', ['stomp']),
]

for url, subprotos in ws_tests:
    try:
        kwargs = {
            'header': [f'Origin: {ORIGIN}', f'Authorization: Bearer {API_KEY}'],
            'timeout': 6,
            'sslopt': {'cert_reqs': ssl.CERT_NONE},
        }
        if subprotos:
            kwargs['subprotocols'] = subprotos
        ws = websocket.create_connection(url, **kwargs)
        proto = ws.subprotocol if hasattr(ws, 'subprotocol') else '?'
        print(f'OK  {url} subproto={subprotos} -> connected (negotiated={proto})')
        try:
            ws.settimeout(3)
            msg = ws.recv()
            print(f'  RECV: {msg[:200]}')
        except:
            pass
        ws.close()
    except Exception as e:
        err = str(e)[:100]
        print(f'FAIL {url} subproto={subprotos} -> {err}')

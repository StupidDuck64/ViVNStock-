import requests, json, time

API_KEY = 'eyJvcmciOiJkbnNlIiwiaWQiOiI3M2JlOGU3MzFhZWQ0MTFkODA5ODYxZDRiN2IxZWM4YSIsImgiOiJtdXJtdXIxMjgifQ=='
now = int(time.time())

# Test 1: DNSE REST chart API (1m candles)
params = {'from': now - 86400, 'to': now, 'symbol': 'VCB', 'resolution': '1'}
headers = {'Authorization': f'Bearer {API_KEY}'}
resp = requests.get('https://services.entrade.com.vn/chart-api/v2/ohlcs/stock', params=params, headers=headers, timeout=10)
print(f'REST Status: {resp.status_code}')
data = resp.json()
print(f'Keys: {list(data.keys())}')
n = len(data.get('t', []))
print(f'Candles: {n}')
if n > 0:
    print(f'Last: time={data["t"][-1]}, O={data["o"][-1]}, H={data["h"][-1]}, L={data["l"][-1]}, C={data["c"][-1]}, V={data["v"][-1]}')
    print(f'First: time={data["t"][0]}, C={data["c"][0]}')

# Test 2: Check rate limit
print('\n--- Rate limit test (3 quick requests) ---')
for i in range(3):
    r = requests.get('https://services.entrade.com.vn/chart-api/v2/ohlcs/stock',
                     params={'from': now - 3600, 'to': now, 'symbol': 'FPT', 'resolution': '1'},
                     headers=headers, timeout=10)
    print(f'Req {i+1}: status={r.status_code}, candles={len(r.json().get("t", []))}')

# Test 3: Daily data
print('\n--- Daily data test ---')
r = requests.get('https://services.entrade.com.vn/chart-api/v2/ohlcs/stock',
                 params={'from': 1420070400, 'to': now, 'symbol': 'VCB', 'resolution': 'D'},
                 headers=headers, timeout=10)
d = r.json()
print(f'Daily candles: {len(d.get("t", []))} (from 2015)')

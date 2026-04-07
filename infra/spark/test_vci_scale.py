import requests, time, warnings
warnings.filterwarnings('ignore')
now = int(time.time())
from_ts = now - 86400*2
api_key = 'eyJvcmciOiJkbnNlIiwiaWQiOiI3M2JlOGU3MzFhZWQ0MTFkODA5ODYxZDRiN2IxZWM4YSIsImgiOiJtdXJtdXIxMjgifQ=='
r = requests.get('https://services.entrade.com.vn/chart-api/v2/ohlcs/stock', params={'symbol':'VCB','resolution':'1','from':from_ts,'to':now}, headers={'Authorization':'Bearer '+api_key}, timeout=10)
d = r.json()
c = d.get('c') or []
if c: print('DNSE VCB close[-1]=%s n=%d' % (c[-1], len(c)))

# VCI direct
r2 = requests.post('https://trading.vietcap.com.vn/api/chart/OHLCChart/gap',
    json={'timeFrame':'ONE_MINUTE','symbols':['VCB'],'from':from_ts,'to':now},
    headers={'Accept':'application/json','Content-Type':'application/json',
             'Referer':'https://trading.vietcap.com.vn/','Origin':'https://trading.vietcap.com.vn/',
             'User-Agent':'Mozilla/5.0 Chrome/120'},
    timeout=15, verify=False)
body = r2.json()
data = body[0]
keys = list(data.keys())
print('VCI raw keys=%s' % keys)
c2 = data.get('c') or []
t2 = data.get('t') or []
if c2: print('VCI VCB close[-1]=%s n=%d' % (c2[-1], len(c2)))
if t2: print('VCI time[0]=%s type=%s' % (t2[0], type(t2[0]).__name__))
# Test long history
from_3y = now - 86400*900
r3 = requests.post('https://trading.vietcap.com.vn/api/chart/OHLCChart/gap',
    json={'timeFrame':'ONE_MINUTE','symbols':['VCB'],'from':from_3y,'to':now},
    headers={'Accept':'application/json','Content-Type':'application/json',
             'Referer':'https://trading.vietcap.com.vn/','Origin':'https://trading.vietcap.com.vn/',
             'User-Agent':'Mozilla/5.0 Chrome/120'},
    timeout=30, verify=False)
body3 = r3.json()
data3 = body3[0]
t3 = data3.get('t') or []
c3 = data3.get('c') or []
print('VCI 900-day history: n=%d first_t=%s last_t=%s first_c=%s' % (len(t3), t3[0] if t3 else None, t3[-1] if t3 else None, c3[0] if c3 else None))

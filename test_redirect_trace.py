import urllib.request
import urllib.error

class TraceRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        print(f"\n[Redirect] HTTP {code} -> {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)

url = 'http://127.0.0.1:3100/airflow/'
print("Tracing HTTP requests from:", url)

opener = urllib.request.build_opener(TraceRedirectHandler)
urllib.request.install_opener(opener)

try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        print(f"\n[Final] Code: {response.getcode()} URL: {response.geturl()}")
except urllib.error.HTTPError as e:
    print(f"\n[HTTP Error] Code: {e.code}")
    print(e.read().decode('utf-8')[:200])
except Exception as e:
    print(f"\n[Generic/Socket Error] {type(e).__name__}: {str(e)}")

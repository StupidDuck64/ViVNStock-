import urllib.request
import urllib.error

url = 'http://127.0.0.1:3100/airflow/'
print("Testing URL:", url)

try:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        print("Status Code:", response.getcode())
        print("\nHeaders:")
        for k, v in response.headers.items():
            print(f"  {k}: {v}")
except urllib.error.HTTPError as e:
    print("HTTP Error Code:", e.code)
    print("\nHeaders:")
    for k, v in e.headers.items():
        print(f"  {k}: {v}")
except Exception as e:
    print("Generic Error:", str(e))

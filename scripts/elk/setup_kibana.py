import requests
import json

KIBANA_URL = "http://localhost:5601"
HEADERS = {"kbn-xsrf": "true", "Content-Type": "application/json"}

print("Creating Index Pattern for 'app-logs-*'...")
payload = {
    "attributes": {
        "title": "app-logs-*",
        "timeFieldName": "@timestamp"
    }
}
res = requests.post(
    f"{KIBANA_URL}/api/saved_objects/index-pattern/app-logs-pattern",
    headers=HEADERS,
    data=json.dumps(payload)
)
print("app-logs-* status:", res.status_code, res.text[:100])

print("Creating Index Pattern for 'vivnstock-logs-*'...")
payload2 = {
    "attributes": {
        "title": "vivnstock-logs-*",
        "timeFieldName": "@timestamp"
    }
}
res2 = requests.post(
    f"{KIBANA_URL}/api/saved_objects/index-pattern/vivnstock-logs-pattern",
    headers=HEADERS,
    data=json.dumps(payload2)
)
print("vivnstock-logs-* status:", res2.status_code, res2.text[:100])

print("\nSetting default index pattern to 'app-logs-*'...")
payload3 = {
    "value": "app-logs-pattern"
}
res3 = requests.post(
    f"{KIBANA_URL}/api/kibana/settings/defaultIndex",
    headers=HEADERS,
    data=json.dumps(payload3)
)
print("default index status:", res3.status_code, res3.text[:100])

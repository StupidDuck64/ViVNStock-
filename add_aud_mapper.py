import json

#check this path?#

path = r'c:\Workspace\RnD\lakehouse-oss\infra\keycloak\data-platform.json'

with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

for client in data.get("clients", []):
    if client.get("clientId") == "lakehouse-portal":
        mappers = client.get("protocolMappers", [])
        
        # Check if audience mapper exists
        exists = any(m.get("protocolMapper") == "oidc-audience-mapper" for m in mappers)
        
        if not exists:
            mappers.append({
                "name": "audience mapper",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-audience-mapper",
                "consentRequired": False,
                "config": {
                    "included.client.audience": "lakehouse-portal",
                    "id.token.claim": "true",
                    "access.token.claim": "true"
                }
            })
            client["protocolMappers"] = mappers
            print("Added audience mapper.")
        else:
            print("Audience mapper already exists.")
            
with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

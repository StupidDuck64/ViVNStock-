import json

path = r'c:\Workspace\RnD\lakehouse-oss\infra\keycloak\data-platform.json'

with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 1. Update the realm if it was hardcoded or anything. Safe to leave "data-platform"

# 2. Add client definition if not already present
client_id = "lakehouse-portal"
clients = data.get("clients", [])

exists = any(c.get("clientId") == client_id for c in clients)

if not exists:
    portal_client = {
        "clientId": client_id,
        "name": "Lakehouse Portal",
        "description": "OAuth2 Proxy Client for Portal",
        "enabled": True,
        "protocol": "openid-connect",
        "clientAuthenticatorType": "client-secret",
        "secret": "CHANGE_ME_OAUTH2_PROXY_SECRET",
        "standardFlowEnabled": True,
        "implicitFlowEnabled": False,
        "directAccessGrantsEnabled": True,
        "serviceAccountsEnabled": False,
        "publicClient": False,
        "redirectUris": [
            "http://127.0.0.1:3100/*",
            "http://localhost:3100/*",
            "http://localhost:3000/*"
        ],
        "webOrigins": [
            "http://127.0.0.1:3100",
            "http://localhost:3100",
            "+"
        ],
        "protocolMappers": [
            {
                "name": "username",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-property-mapper",
                "config": {
                    "userinfo.token.claim": "true",
                    "user.attribute": "username",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "claim.name": "preferred_username",
                    "jsonType.label": "String"
                }
            },
            {
                "name": "email",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-property-mapper",
                "config": {
                    "userinfo.token.claim": "true",
                    "user.attribute": "email",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "claim.name": "email",
                    "jsonType.label": "String"
                }
            },
            {
                "name": "groups",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-group-membership-mapper",
                "config": {
                    "claim.name": "groups",
                    "full.path": "false",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true"
                }
            },
            {
                "name": "roles",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-realm-role-mapper",
                "config": {
                    "claim.name": "roles",
                    "jsonType.label": "String",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true",
                    "multivalued": "true"
                }
            }
        ]
    }
    clients.append(portal_client)
    data["clients"] = clients
    print("Added lakehouse-portal client to data-platform.json")
else:
    print("lakehouse-portal client already exists in data-platform.json")

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

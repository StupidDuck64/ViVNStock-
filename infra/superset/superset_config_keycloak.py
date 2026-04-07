from flask_appbuilder.security.manager import AUTH_OAUTH
from superset.security import SupersetSecurityManager
import os
import logging

AUTH_TYPE = AUTH_OAUTH

AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Public"

# Allow insecure transport for development
os.environ['AUTHLIB_INSECURE_TRANSPORT'] = 'true'

OAUTH_PROVIDERS = [
    {
        "name": "keycloak",
        "icon": "fa-key",
        "token_key": "access_token",
        "remote_app": {
            "client_id": "superset",
            "client_secret": "CHANGE_ME_SUPERSET_SECRET",
            "client_kwargs": {
                "scope": "openid profile email roles groups"
            },
            # Sử dụng service name 'keycloak' từ docker-compose cho container communication
            # Keycloak được config với KC_HOSTNAME=localhost để issuer claim match
            "server_metadata_url": "http://keycloak:8080/realms/data-platform/.well-known/openid-configuration",
            "access_token_url": "http://keycloak:8080/realms/data-platform/protocol/openid-connect/token",
            "authorize_url": "http://192.168.26.181:8084/realms/data-platform/protocol/openid-connect/auth",
            "api_base_url": "http://keycloak:8080/realms/data-platform/protocol/",
            "userinfo_endpoint": "http://keycloak:8080/realms/data-platform/protocol/openid-connect/userinfo",
        },
    }
]

# Custom Security Manager to map Keycloak roles to Superset roles
class KeycloakSecurityManager(SupersetSecurityManager):
    def oauth_user_info(self, provider, response=None):
        if provider == 'keycloak':
            me = self.appbuilder.sm.oauth_remotes[provider].get('userinfo').json()
            
            logging.info(f"OAuth user info: {me}")
            
            # Get roles from Keycloak token
            roles = me.get('roles', [])
            
            # Map Keycloak roles to Superset roles
            if 'superset-admin' in roles or 'platform-admin' in roles:
                role = 'Admin'
            elif 'superset-editor' in roles or 'data-engineer' in roles:
                role = 'Alpha'
            elif 'superset-viewer' in roles or 'data-analyst' in roles or 'business-user' in roles:
                role = 'Gamma'
            else:
                role = 'Public'
            
            logging.info(f"Mapped role: {role} for user: {me.get('preferred_username')}")
            
            return {
                'username': me.get('preferred_username', ''),
                'email': me.get('email', ''),
                'first_name': me.get('given_name', ''),
                'last_name': me.get('family_name', ''),
                'role_keys': [role]
            }
        
        return {}

CUSTOM_SECURITY_MANAGER = KeycloakSecurityManager

# Enable detailed OAuth logging for debugging
logging.getLogger('flask_appbuilder.security.views').setLevel(logging.DEBUG)
logging.getLogger('authlib').setLevel(logging.DEBUG)
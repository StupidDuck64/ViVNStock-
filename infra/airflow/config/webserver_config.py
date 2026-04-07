"""Cấu hình Airflow Webserver tích hợp Keycloak OAuth2.

Mục tiêu:
- Đăng nhập SSO qua Keycloak
- Tự động map role Keycloak sang role Airflow
- Hỗ trợ auto-register user lần đăng nhập đầu
"""
import os
import logging
from flask_appbuilder.security.manager import AUTH_OAUTH
from airflow.providers.fab.auth_manager.security_manager.override import FabAirflowSecurityManagerOverride

# Bật log chi tiết để debug OAuth handshake.
logging.getLogger("flask_appbuilder").setLevel(logging.DEBUG)
logging.getLogger("authlib").setLevel(logging.DEBUG)

# Cho phép HTTP (không TLS) trong môi trường local/dev.
os.environ['AUTHLIB_INSECURE_TRANSPORT'] = 'true'

# Xác định cơ chế auth chính là OAuth.
AUTH_TYPE = AUTH_OAUTH

# Tự tạo user trong Airflow DB khi đăng nhập lần đầu.
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Admin"  # Default role for auto-registered users

# Allow users to self-register with Keycloak
AUTH_ROLE_ADMIN = 'Admin'
AUTH_ROLE_PUBLIC = 'Public'

# Cấu hình OAuth provider: Keycloak realm data-platform.
OAUTH_PROVIDERS = [
    {
        'name': 'keycloak',
        'icon': 'fa-key',
        'token_key': 'access_token',
        'remote_app': {
            'client_id': 'airflow',
            'client_secret': 'CHANGE_ME_AIRFLOW_SECRET',
            'client_kwargs': {
                'scope': 'openid email profile'
            },
            # Use service name for container-to-container communication
            'server_metadata_url': 'http://keycloak:8080/realms/data-platform/.well-known/openid-configuration',
            'access_token_url': 'http://keycloak:8080/realms/data-platform/protocol/openid-connect/token',
            # Use localhost for browser redirect (external access)
            'authorize_url': 'http://127.0.0.1:18084/realms/data-platform/protocol/openid-connect/auth',
            'api_base_url': 'http://keycloak:8080/realms/data-platform/protocol/openid-connect/',
            'redirect_uri': 'http://127.0.0.1:8085/auth/oauth-authorized/keycloak',
        }
    }
]


class KeycloakSecurityManager(FabAirflowSecurityManagerOverride):
    """Security manager tùy biến để map role từ Keycloak sang Airflow."""
    
    def oauth_user_info(self, provider, response=None):
        """
        Extract user information from OAuth provider response
        
        Args:
            provider: OAuth provider name
            response: OAuth response
            
        Returns:
            Dictionary with user information
        """
        if provider == 'keycloak':
            try:
                # Get user info from Keycloak using the correct endpoint
                remote = self.appbuilder.sm.oauth_remotes[provider]
                resp = remote.get('userinfo')
                me = resp.json()
                
                logging.info(f"Keycloak OAuth user info: {me}")
                
                # Extract roles from token
                roles = me.get('roles', [])
                groups = me.get('groups', [])
                
                logging.info(f"User roles: {roles}")
                logging.info(f"User groups: {groups}")
                
                # Map role theo policy của hệ thống.
                # Airflow roles tiêu chuẩn: Admin, Op, User, Viewer, Public.
                if 'airflow-admin' in roles or 'platform-admin' in roles:
                    role_name = 'Admin'
                elif 'airflow-user' in roles or 'data-engineer' in roles:
                    role_name = 'Op'
                elif 'airflow-viewer' in roles or 'data-analyst' in roles:
                    role_name = 'Viewer'
                else:
                    role_name = 'Public'
                
                logging.info(f"Mapped Airflow role: {role_name} for user: {me.get('preferred_username')}")
                
                user_info = {
                    'username': me.get('preferred_username', ''),
                    'email': me.get('email', ''),
                    'first_name': me.get('given_name', ''),
                    'last_name': me.get('family_name', ''),
                    'role_keys': [role_name]
                }
                
                # Update user role in database if user exists
                username = user_info.get('username')
                if username:
                    user = self.find_user(username=username)
                    if user:
                        role = self.find_role(role_name)
                        if role and role not in user.roles:
                            logging.info(f"Syncing role {role_name} for user {username}")
                            user.roles = [role]
                            self.update_user(user)
                
                return user_info
            except Exception as e:
                logging.error(f"Error getting user info from Keycloak: {e}")
                import traceback
                logging.error(traceback.format_exc())
                return {}
        
        return {}


# Kích hoạt security manager tùy biến.
SECURITY_MANAGER_CLASS = KeycloakSecurityManager

# Additional Flask App Builder configurations
CSRF_ENABLED = True
WTF_CSRF_ENABLED = True

# Session configuration
PERMANENT_SESSION_LIFETIME = 3600  # 1 hour

# Cache configuration
CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_REDIS_URL': 'redis://redis:6379/1',
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_KEY_PREFIX': 'airflow_',
}

# Rate limiting
RATELIMIT_ENABLED = True
RATELIMIT_STORAGE_URL = 'redis://redis:6379/2'

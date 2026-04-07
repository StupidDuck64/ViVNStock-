import os

# Secret key — read from env (vault-entrypoint.sh exports SECRET_KEY from Vault).
SECRET_KEY = os.environ.get('SECRET_KEY') or os.environ.get('SUPERSET_SECRET_KEY', 'your_superset_key')

# Superset metadata database — POSTGRES_PASSWORD is injected by vault-entrypoint.sh.
_pg_user = os.environ.get('POSTGRES_USER', 'admin')
_pg_password = os.environ.get('POSTGRES_PASSWORD', 'admin')
SQLALCHEMY_DATABASE_URI = f'postgresql://{_pg_user}:{_pg_password}@postgres/superset'

# Results backend for async queries - use Redis
from cachelib.redis import RedisCache
RESULTS_BACKEND = RedisCache(
    host='redis',
    port=6379,
    key_prefix='superset_results',
    default_timeout=86400  # 24 hours
)

# Celery Configuration - using Redis
class CeleryConfig:
    broker_url = 'redis://redis:6379/0'
    result_backend = 'redis://redis:6379/1'
    task_serializer = 'json'
    result_serializer = 'json'
    accept_content = ['json']
    timezone = 'UTC'
    enable_utc = True

CELERY_CONFIG = CeleryConfig

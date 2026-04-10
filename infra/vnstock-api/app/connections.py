import logging
import time

import redis.asyncio as aioredis
import trino

from app.config import REDIS_HOST, REDIS_PORT, TRINO_HOST, TRINO_PORT, TRINO_USER, TRINO_CATALOG

logger = logging.getLogger("vnstock-api.connections")

_redis_pool: aioredis.Redis | None = None

# Trino retry config
TRINO_MAX_RETRIES = 3
TRINO_RETRY_BACKOFF = 1  # seconds, doubles each retry


async def get_redis() -> aioredis.Redis:
    """Get async Redis client (singleton, reuses connection pool)."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            max_connections=20,       # Limit pool size for 32GB machine
            health_check_interval=30,
        )
        logger.info("Redis pool created: %s:%d (max_connections=20)", REDIS_HOST, REDIS_PORT)
    return _redis_pool


def get_trino_connection() -> trino.dbapi.Connection:
    """
    Create a new Trino connection per call, with retry and exponential backoff.

    The Trino DBAPI driver does not officially support connection pooling.
    Each /history query creates 1 connection → execute → close.
    With 2 uvicorn workers, max concurrent = ~10 queries (default thread pool).

    Retry logic: 3 attempts, backoff 1s → 2s → 4s.
    Handles the case where Trino is not yet ready after Docker starts.
    """
    last_err = None
    for attempt in range(TRINO_MAX_RETRIES):
        try:
            conn = trino.dbapi.connect(
                host=TRINO_HOST,
                port=TRINO_PORT,
                user=TRINO_USER,
                catalog=TRINO_CATALOG,
                schema="bronze",
                http_scheme="http",
                verify=False,
                request_timeout=30,
            )
            # Verify connection is alive with a lightweight query
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            return conn
        except Exception as e:
            last_err = e
            if attempt < TRINO_MAX_RETRIES - 1:
                wait = TRINO_RETRY_BACKOFF * (2 ** attempt)
                logger.warning(
                    "Trino connection attempt %d/%d failed: %s. Retrying in %ds...",
                    attempt + 1, TRINO_MAX_RETRIES, e, wait,
                )
                time.sleep(wait)
            else:
                logger.error(
                    "Trino connection failed after %d attempts: %s",
                    TRINO_MAX_RETRIES, e,
                )
    raise last_err


def check_trino_health() -> bool:
    """Check if Trino is ready (used by /api/health)."""
    try:
        conn = trino.dbapi.connect(
            host=TRINO_HOST,
            port=TRINO_PORT,
            user=TRINO_USER,
            catalog=TRINO_CATALOG,
            schema="bronze",
            http_scheme="http",
            verify=False,
            request_timeout=5,
        )
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        conn.close()
        return True
    except Exception:
        return False


async def close_all():
    """Close all connections on shutdown."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None
        logger.info("Redis pool closed")

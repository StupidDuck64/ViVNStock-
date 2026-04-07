"""VNStock API Configuration."""

import os

# Redis
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Trino (queries Iceberg tables)
TRINO_HOST = os.getenv("TRINO_HOST", "trino")
TRINO_PORT = int(os.getenv("TRINO_PORT", "8080"))
TRINO_USER = os.getenv("TRINO_USER", "vnstock")
TRINO_CATALOG = os.getenv("TRINO_CATALOG", "iceberg")

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Symbols
DEFAULT_SYMBOLS = os.getenv(
    "VNSTOCK_SYMBOLS",
    "VCB,HPG,FPT,VIC,VHM,TCB,MBB,ACB,SSI,VND,GAS,VNM,MSN,MWG,PLX"
)

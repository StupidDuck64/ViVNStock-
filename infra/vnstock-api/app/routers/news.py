"""
GET /api/news — Latest financial news from Redis.

Data is populated by vnstock_news_crawler Spark job.
"""

import json

from fastapi import APIRouter, Query
from app.connections import get_redis

router = APIRouter(prefix="/api", tags=["news"])


@router.get("/news")
async def get_news(
    source: str | None = Query(None, description="Filter by source: cafef, vietstock, vneconomy"),
    limit: int = Query(50, ge=1, le=200),
):
    r = await get_redis()
    key = f"vnstock:news:{source}" if source else "vnstock:news:all"
    items = await r.zrevrange(key, 0, limit - 1)
    return [json.loads(item) for item in items]

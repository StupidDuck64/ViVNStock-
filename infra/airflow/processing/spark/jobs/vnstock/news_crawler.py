import hashlib
import json
import logging
import os
import time
from datetime import datetime

import redis
import requests
from bs4 import BeautifulSoup

from pyspark.sql import SparkSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vnstock_news")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

SOURCES = {
    "cafef": {
        "base_url": "https://cafef.vn/thi-truong-chung-khoan.chn",
        "article_selector": "div.tlitem h3 a",
        "domain": "https://cafef.vn",
    },
    "vietstock": {
        "base_url": "https://vietstock.vn/chung-khoan.htm",
        "article_selector": "h4.title a, h3.title a",
        "domain": "https://vietstock.vn",
    },
    "vneconomy": {
        "base_url": "https://vneconomy.vn/chung-khoan.htm",
        "article_selector": "h3.story__title a, h2.story__title a",
        "domain": "https://vneconomy.vn",
    },
}


def _article_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def scrape_source(source_name: str, config: dict, max_pages: int = 3):
    """Scrape article links and titles from a source."""
    articles = []
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    for page in range(1, max_pages + 1):
        url = config["base_url"] if page == 1 else f"{config['base_url']}?page={page}"
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("[%s] page %d failed: %s", source_name, page, e)
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.select(config["article_selector"])

        for a_tag in links:
            href = a_tag.get("href", "")
            title = a_tag.get_text(strip=True)
            if not href or not title:
                continue
            if not href.startswith("http"):
                href = config["domain"] + href

            articles.append({
                "id": _article_id(href),
                "title": title,
                "url": href,
                "source": source_name,
                "crawled_at": int(time.time() * 1000),
                "published_at": int(time.time() * 1000),
            })

        time.sleep(1)

    logger.info("[%s] scraped %d articles", source_name, len(articles))
    return articles


def write_to_redis(articles):
    """Store articles in Redis sorted sets + individual article keys."""
    if not articles:
        return
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True,
                        socket_connect_timeout=5)
        pipe = r.pipeline()
        for art in articles:
            score = art.get("published_at", art["crawled_at"])
            member = json.dumps({"id": art["id"], "title": art["title"],
                                  "url": art["url"], "source": art["source"]},
                                 ensure_ascii=False)
            pipe.zadd("vnstock:news:all", {member: score})
            pipe.zadd(f"vnstock:news:{art['source']}", {member: score})
            pipe.set(f"vnstock:news:article:{art['id']}", json.dumps(art, ensure_ascii=False))

        # Trim to latest 500 per set
        pipe.zremrangebyrank("vnstock:news:all", 0, -501)
        for src in SOURCES:
            pipe.zremrangebyrank(f"vnstock:news:{src}", 0, -201)
        pipe.execute()
        logger.info("Wrote %d articles to Redis", len(articles))
    except redis.ConnectionError as e:
        logger.error("Redis connection failed: %s", e)
        raise


def main():
    import argparse
    p = argparse.ArgumentParser(description="VNStock News Crawler")
    p.add_argument("--max-pages", type=int, default=3)
    args = p.parse_args()

    # SparkSession is required by SparkSubmitOperator but we use it minimally
    spark = SparkSession.builder \
        .appName("VNStock-News-Crawler") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    all_articles = []
    for source_name, config in SOURCES.items():
        articles = scrape_source(source_name, config, max_pages=args.max_pages)
        all_articles.extend(articles)

    logger.info("Total articles: %d", len(all_articles))
    write_to_redis(all_articles)
    spark.stop()


if __name__ == "__main__":
    main()

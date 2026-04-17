"""
VNStock News Crawler

Scrapes financial news from Vietnamese sources:
  - CafeF (cafef.vn)
  - Vietstock (vietstock.vn)
  - VnEconomy (vneconomy.vn)

Stores results into Redis for real-time API serving.

Redis key structure:
  vnstock:news:all           → sorted set (score=publish_timestamp)
  vnstock:news:{source}      → sorted set by source
  vnstock:news:article:{id}  → article JSON detail

Lakehouse table:
    iceberg.bronze.vnstock_news

Usage:
  spark-submit vnstock/vnstock_news_crawler.py --max-pages 3
"""

import hashlib
import json
import logging
import os
import time
from urllib.parse import urljoin, urlsplit, urlunsplit

import redis
import requests
from bs4 import BeautifulSoup

from pyspark.sql import SparkSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vnstock_news")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
NEWS_SEEN_IDS_KEY = "vnstock:news:seen_ids"
NEWS_SEEN_IDS_MAX = int(os.getenv("VNSTOCK_NEWS_SEEN_IDS_MAX", "5000"))
NEWS_ICEBERG_TABLE = os.getenv("VNSTOCK_NEWS_ICEBERG_TABLE", "iceberg.bronze.vnstock_news")

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


def _canonicalize_url(url: str, domain: str) -> str:
    """Normalize URL so equivalent links map to one article id."""
    raw = (url or "").strip()
    if not raw:
        return ""

    absolute = urljoin(domain, raw)
    parsed = urlsplit(absolute)

    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Drop query + fragment to reduce tracking-parameter duplicates.
    return urlunsplit((scheme, netloc, path, "", ""))


def _article_id(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:12]


def scrape_source(source_name: str, config: dict, max_pages: int = 3):
    """Scrape article links and titles from a source."""
    articles = []
    seen_urls = set()
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

            href = _canonicalize_url(href, config["domain"])
            if not href or href in seen_urls:
                continue
            seen_urls.add(href)

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


def _dedup_in_batch(articles: list[dict]) -> list[dict]:
    """Deduplicate scraped rows in memory by article id before Redis writes."""
    latest_by_id = {}
    for art in articles:
        art_id = art["id"]
        prev = latest_by_id.get(art_id)
        if prev is None or art.get("crawled_at", 0) >= prev.get("crawled_at", 0):
            latest_by_id[art_id] = art
    return list(latest_by_id.values())


def write_to_lakehouse(
    spark: SparkSession,
    articles: list[dict],
    table_name: str = NEWS_ICEBERG_TABLE,
) -> int:
    """Store articles into Iceberg Bronze and skip ids that already exist."""
    if not articles:
        logger.info("Lakehouse sync skipped: no articles")
        return 0

    db_name = ".".join(table_name.split(".")[:-1])
    if db_name:
        spark.sql(f"CREATE DATABASE IF NOT EXISTS {db_name}")

    incoming_count = len(articles)
    incoming_df = spark.createDataFrame(articles).select(
        "id", "title", "url", "source", "crawled_at", "published_at"
    )

    if spark.catalog.tableExists(table_name):
        existing_ids = spark.table(table_name).select("id").dropDuplicates(["id"])
        to_write = incoming_df.join(existing_ids, on="id", how="left_anti").cache()
        new_count = to_write.count()
        if new_count == 0:
            to_write.unpersist()
            logger.info("Lakehouse sync skipped: all %d rows already exist in %s", incoming_count, table_name)
            return 0

        to_write.writeTo(table_name).append()
        to_write.unpersist()
    else:
        incoming_df.writeTo(table_name) \
            .tableProperty("format-version", "2") \
            .create()
        new_count = incoming_count

    logger.info(
        "Lakehouse sync complete: %d incoming -> %d new rows in %s",
        incoming_count,
        new_count,
        table_name,
    )
    return new_count


def write_to_redis(articles):
    """Store articles in Redis sorted sets + individual article keys."""
    if not articles:
        return
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True,
                        socket_connect_timeout=5)
        pipe = r.pipeline()

        total = len(articles)
        new_count = 0
        skipped_count = 0

        for art in articles:
            score = art.get("published_at", art["crawled_at"])
            # Cross-run dedup: only first time an article id is seen gets written.
            is_new = r.zadd(NEWS_SEEN_IDS_KEY, {art["id"]: score}, nx=True)
            if not is_new:
                skipped_count += 1
                continue

            member = json.dumps({"id": art["id"], "title": art["title"],
                                  "url": art["url"], "source": art["source"]},
                                 ensure_ascii=False)
            pipe.zadd("vnstock:news:all", {member: score})
            pipe.zadd(f"vnstock:news:{art['source']}", {member: score})
            pipe.set(f"vnstock:news:article:{art['id']}", json.dumps(art, ensure_ascii=False))
            new_count += 1

        # Trim to latest 500 per set
        pipe.zremrangebyrank("vnstock:news:all", 0, -501)
        for src in SOURCES:
            pipe.zremrangebyrank(f"vnstock:news:{src}", 0, -201)
        pipe.zremrangebyrank(NEWS_SEEN_IDS_KEY, 0, -(NEWS_SEEN_IDS_MAX + 1))

        pipe.execute()
        logger.info(
            "Processed %d articles -> wrote %d new, skipped %d duplicates",
            total,
            new_count,
            skipped_count,
        )
    except redis.ConnectionError as e:
        logger.error("Redis connection failed: %s", e)
        raise


def main():
    import argparse
    p = argparse.ArgumentParser(description="VNStock News Crawler")
    p.add_argument("--max-pages", type=int, default=3)
    p.add_argument("--lakehouse-table", default=NEWS_ICEBERG_TABLE)
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

    deduped_articles = _dedup_in_batch(all_articles)
    logger.info(
        "Total scraped: %d, unique in batch: %d",
        len(all_articles),
        len(deduped_articles),
    )

    write_to_lakehouse(spark, deduped_articles, table_name=args.lakehouse_table)
    write_to_redis(deduped_articles)
    spark.stop()


if __name__ == "__main__":
    main()

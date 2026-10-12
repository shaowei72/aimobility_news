import requests
import feedparser
from datetime import datetime, timezone, timedelta
import random

from .models import Article
from .config import FEEDS, RECENT_HOURS
from .esri_search import fetch_esri_articles

def load_feed(url: str):
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20
    )

    response.raise_for_status()

    return feedparser.parse(response.content)



def fetch_articles():
    articles = []

    for source, url in FEEDS.items():
        feed = load_feed(url)

        for entry in feed.entries:
            published_at = None
            if entry.get("published_parsed"):
                published_at = datetime(
                    *entry.published_parsed[:6],
                    tzinfo=timezone.utc
                )
            
            article = Article(
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                source=source,
                published_at=published_at,
                summary=entry.get("summary")
            )

            articles.append(article)

    return articles

def filter_recent_articles(articles, hours=RECENT_HOURS):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    recent_articles = []

    for article in articles:
        if article.published_at is None:
            continue

        if article.published_at >= cutoff:
            recent_articles.append(article)

    return recent_articles

def deduplicate_articles(articles):
    seen_urls = set()
    unique_articles = []

    for article in articles:
        if article.url in seen_urls:
            continue

        seen_urls.add(article.url)
        unique_articles.append(article)

    return unique_articles


if __name__ == "__main__":
    # articles = fetch_articles() + fetch_esri_articles()
    articles= fetch_articles()
    recent_articles = filter_recent_articles(articles)
    unique_articles = deduplicate_articles(recent_articles)

    print(f"Fetched {len(articles)} articles")
    print(f"Published in last {RECENT_HOURS} hours: {len(recent_articles)}")
    print(f"Unique: {len(unique_articles)}")

    for article in unique_articles:
        print()
        print(article.title)
        print(article.source)
        print(article.published_at)
        print(article.url)


    # for article in random.sample(unique_articles,  min(10, len(unique_articles))):
    #     print()
    #     print(article.title)
    #     print(article.source)
    #     print(article.published_at)
    #     print(article.url)


    # test_articles = [
    #     Article(
    #         title="Article A",
    #         url="https://example.com/a",
    #         source="Source 1",
    #         published_at=None,
    #         summary=None
    #     ),
    #     Article(
    #         title="Article B",
    #         url="https://example.com/b",
    #         source="Source 2",
    #         published_at=None,
    #         summary=None
    #     ),
    #     Article(
    #         title="Article A duplicate",
    #         url="https://example.com/a",
    #         source="Source 3",
    #         published_at=None,
    #         summary=None
    #     ),
    #     ]

    # unique_articles = deduplicate_articles(test_articles)

    # print(f"Before: {len(test_articles)}")
    # print(f"After: {len(unique_articles)}")

    # for article in unique_articles:
    #     print(article.title, article.url)
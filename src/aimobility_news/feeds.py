import feedparser
from datetime import datetime, timezone
import random

from .models import Article
from .config import FEEDS

def fetch_articles():
    articles = []

    for source, url in FEEDS.items():
        feed = feedparser.parse(url)

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

if __name__ == "__main__":
    articles = fetch_articles()

    print(f"Fetched {len(articles)} articles")

    for article in random.sample(articles,  min(10, len(articles))):
        print()
        print(article.title)
        print(article.source)
        print(article.published_at)
        print(article.url)
import requests
import feedparser
from datetime import datetime, timezone, timedelta
import random
import trafilatura
from bs4 import BeautifulSoup

from .models import Article
from .config import (
    FEEDS,
    RECENT_HOURS,
    FULL_TEXT_MIN_WORDS,
    PAGE_FETCH_SOURCES,
)
from .esri_search import fetch_esri_articles


def html_to_text(html: str | None) -> str | None:
    if not html:
        return None
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    return text or None


def extract_content(entry, summary: str | None) -> str | None:
    # Full text is usually in entry.content (e.g. Substack, OGC), but some
    # feeds (e.g. IEEE Spectrum) put the full article in the summary instead.
    # Take the longest candidate, and only treat it as full text if it is
    # long enough; short teasers or image-only bodies are not full text.
    candidates = [
        html_to_text(c.get("value")) for c in entry.get("content", [])
    ]
    candidates.append(summary)

    longest = max(
        (text for text in candidates if text),
        key=lambda text: len(text.split()),
        default=None,
    )

    if longest and len(longest.split()) >= FULL_TEXT_MIN_WORDS:
        return longest

    return None


def fetch_page_text(url: str) -> str | None:
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20
    )

    response.raise_for_status()

    return trafilatura.extract(
        response.text,
        include_comments=False,
        include_tables=True
    )


def add_page_content(articles):
    # Only for sources in PAGE_FETCH_SOURCES, and only for articles that
    # still lack full text. Call after filtering, so old entries are not fetched.
    for article in articles:
        if article.source not in PAGE_FETCH_SOURCES or article.content:
            continue

        try:
            text = fetch_page_text(article.url)
        except requests.RequestException as e:
            print(f"WARNING: page fetch failed for {article.url}: {e}")
            continue

        if text and len(text.split()) >= FULL_TEXT_MIN_WORDS:
            article.content = text
        else:
            print(f"WARNING: no article text extracted from {article.url}")

    return articles


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
        try:
            feed = load_feed(url)
        except requests.RequestException as e:
            print(f"WARNING: skipping {source}: {e}")
            continue

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()

            # Without a link the article cannot be deduplicated or opened
            if not title or not url:
                continue

            published_at = None
            if entry.get("published_parsed"):
                published_at = datetime(
                    *entry.published_parsed[:6],
                    tzinfo=timezone.utc
                )

            summary = html_to_text(entry.get("summary"))

            article = Article(
                title=title,
                url=url,
                source=source,
                published_at=published_at,
                summary=summary,
                content=extract_content(entry, summary),
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


def inspect_feed_structure(source: str):
    """
    Inspect the raw RSS fields for one source in FEEDS.
    Useful for identifying where article text is stored.
    """
    if source not in FEEDS:
        print(f"Source not found: {source}")
        return

    feed = load_feed(FEEDS[source])

    print(f"\nSource: {source}")
    print(f"Number of entries: {len(feed.entries)}")

    if not feed.entries:
        return

    entry = feed.entries[0]

    print(f"\nTitle: {entry.get('title')}")
    print(f"URL: {entry.get('link')}")

    print("\n--- Available fields ---")

    for key, value in entry.items():
        print(f"{key}: {type(value).__name__}")

    print("\n--- Text fields ---")

    summary = html_to_text(entry.get("summary"))
    content_list = entry.get("content", [])

    print(f"Summary words: {len(summary.split()) if summary else 0}")
    print(f"Content elements: {len(content_list)}")

    for i, content in enumerate(content_list):
        text = html_to_text(content.get("value"))
        print(f"Content[{i}] type: {content.get('type')}")
        print(f"Content[{i}] words: {len(text.split()) if text else 0}")
        print(f"Content[{i}] preview: {(text or '')[:500]}")

    print(f"\nSummary preview: {(summary or '')[:500]}")

    selected = extract_content(entry, summary)
    print(f"\nExtracted content words: {len(selected.split()) if selected else 0}")



def inspect_article_webpage(source: str, limit: int = 5):
    feed = load_feed(FEEDS[source])

    print(f"\nSource: {source}")
    print(f"Available entries: {len(feed.entries)}")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=RECENT_HOURS)
    count = 0

    for entry in feed.entries:
        if not entry.get("published_parsed"):
            continue

        published = datetime(
            *entry.published_parsed[:6],
            tzinfo=timezone.utc
        )

        if published < cutoff:
            continue

        url = entry.get("link")

        if not url:
            continue

        print(f"\nArticle: {entry.get('title')}")
        print(f"Published: {published}")
        print(f"URL: {url}")

        html = trafilatura.fetch_url(url)

        if not html:
            print("Failed to retrieve webpage")
        else:
            text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True
            )

            if text:
                print(f"Extracted words: {len(text.split())}")
                print(f"Preview: {text[:1300]}")
            else:
                print("Failed to extract article text")

        count += 1
        if count >= limit:
            break



if __name__ == "__main__":
    inspect_article_webpage("Google Research")
    inspect_article_webpage("Google DeepMind")

    # inspect_feed_structure("Google Research")
    # inspect_feed_structure("Google DeepMind")

    # articles = fetch_articles() + fetch_esri_articles()
    # articles= fetch_articles()
    # recent_articles = filter_recent_articles(articles)
    # unique_articles = deduplicate_articles(recent_articles)

    # print(f"Fetched {len(articles)} articles")
    # print(f"Published in last {RECENT_HOURS} hours: {len(recent_articles)}")
    # print(f"Unique: {len(unique_articles)}")

    # for article in unique_articles:
    #     print()
    #     print(article.title)
    #     print(article.source)
    #     print(article.published_at)
    #     print(article.url)
    #     print(f"\n-----\nSummary:\n {article.summary}\n")
    #     print(f"\n-----\nFull: {article.content}\n")


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
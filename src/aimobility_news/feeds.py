import requests
import feedparser
from datetime import datetime, timezone, timedelta
import random
import time
import trafilatura
from bs4 import BeautifulSoup

from .models import Article
from .textlen import text_length
from .config import (
    FEEDS,
    RECENT_HOURS,
    FULL_TEXT_MIN_WORDS,
    MAX_CONTENT_WORDS,
    PAGE_FETCH_SOURCES,
    HTTP_TIMEOUT,
    HTTP_TIMEOUT_OVERRIDES,
    HTTP_RETRIES,
    FEED_KEYWORDS,
)
from .esri_search import fetch_esri_articles


def http_get(url: str, timeout: float = HTTP_TIMEOUT) -> requests.Response:
    """GET with HTTP_RETRIES retries on timeouts, connection errors and 5xx.

    4xx responses (403, 404, ...) are not retried: they rarely change on a
    second try. Raises requests.RequestException after the last attempt.
    """
    transient = (
        requests.Timeout,
        requests.ConnectionError,
        requests.exceptions.ChunkedEncodingError,   # "Response ended prematurely"
    )
    for attempt in range(HTTP_RETRIES + 1):
        last = attempt == HTTP_RETRIES
        try:
            response = requests.get(
                url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout
            )
        except transient:
            if last:
                raise
        else:
            if response.status_code < 500 or last:
                response.raise_for_status()
                return response
        time.sleep(2)


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
        key=text_length,
        default=None,
    )

    if longest and text_length(longest) >= FULL_TEXT_MIN_WORDS:
        return longest

    return None


def fetch_page_text(url: str) -> str | None:
    response = http_get(url)

    return trafilatura.extract(
        response.text,
        include_comments=False,
        include_tables=True
    )


def add_page_content(articles):
    # Only for sources in PAGE_FETCH_SOURCES. The page is fetched even when the
    # feed already gave enough text to count as full text (e.g. The Verge's
    # ~150-word opening excerpts), and the longer of the two is kept. If the
    # fetch fails, the feed's text stays. Call after filtering, so old entries
    # are not fetched.
    for article in articles:
        if article.source not in PAGE_FETCH_SOURCES:
            continue

        try:
            text = fetch_page_text(article.url)
        except requests.RequestException as e:
            print(f"WARNING: page fetch failed for {article.url}: {e}")
            continue

        page_words = text_length(text)
        feed_words = text_length(article.content)

        if page_words >= FULL_TEXT_MIN_WORDS and page_words > feed_words:
            article.content = text
        elif not article.content:
            print(f"WARNING: no article text extracted from {article.url}")

    return articles


def load_feed(url: str, timeout: float = HTTP_TIMEOUT):
    return feedparser.parse(http_get(url, timeout).content)


def keyword_filter(articles: list[Article]) -> list[Article]:
    # For high-volume general feeds listed in FEED_KEYWORDS, keep only articles
    # whose title, summary or full text contains one of that source's keywords
    # (case-insensitive), so they are not all sent to the LLM for scoring.
    # Other sources pass through unchanged.
    kept = []
    dropped: dict[str, int] = {}
    for article in articles:
        keywords = FEED_KEYWORDS.get(article.source)
        if keywords:
            text = " ".join(
                t for t in (article.title, article.summary, article.content) if t
            ).lower()
            if not any(k.lower() in text for k in keywords):
                dropped[article.source] = dropped.get(article.source, 0) + 1
                continue
        kept.append(article)
    for source, n in dropped.items():
        print(f"Keyword filter: {n} {source} articles dropped")
    return kept


def fetch_articles(feeds: dict[str, str] | None = None):
    # feeds: {source: url}; defaults to all FEEDS
    articles = []

    for source, url in (feeds or FEEDS).items():
        try:
            feed = load_feed(url, HTTP_TIMEOUT_OVERRIDES.get(source, HTTP_TIMEOUT))
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

    feed = load_feed(FEEDS[source], HTTP_TIMEOUT_OVERRIDES.get(source, HTTP_TIMEOUT))

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

    print(f"Summary words: {text_length(summary)}")
    print(f"Content elements: {len(content_list)}")

    for i, content in enumerate(content_list):
        text = html_to_text(content.get("value"))
        print(f"Content[{i}] type: {content.get('type')}")
        print(f"Content[{i}] words: {text_length(text)}")
        print(f"Content[{i}] preview: {(text or '')[:500]}")

    print(f"\nSummary preview: {(summary or '')[:500]}")

    selected = extract_content(entry, summary)
    print(f"\nExtracted content words: {text_length(selected)}")



def inspect_article_webpage(source: str, limit: int = 5):
    feed = load_feed(FEEDS[source], HTTP_TIMEOUT_OVERRIDES.get(source, HTTP_TIMEOUT))

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

        # Same fetch as the pipeline (add_page_content), so a failure shows
        # the HTTP status or network error instead of a bare None
        try:
            text = fetch_page_text(url)
        except requests.RequestException as e:
            print(f"Failed to retrieve webpage: {e}")
        else:
            if text:
                print(f"Extracted words: {text_length(text)}")
                print(f"Preview: {text[:5000]}")
            else:
                print("Failed to extract article text")

        count += 1
        if count >= limit:
            break


def inspect_extraction(
    sources: list[str],
    hours: int = RECENT_HOURS,
    limit: int = 5,
    preview_chars: int = 600,
):
    """Run the pipeline's text steps for the given sources and show the result.

    Same steps as main.py up to scoring: fetch_articles() -> recency filter ->
    keyword_filter() -> add_page_content(), then text_for_scoring(). For each
    article: where the text came from (feed or page), its length in
    characters and word-equivalents (textlen.py), what scoring receives after
    the MAX_CONTENT_WORDS cap, and a preview. No LLM calls.
    """
    from .scoring import text_for_scoring
    from .config import FEEDS_AI_CN

    # Feeds on hold (e.g. FEEDS_AI_CN, not in FEEDS) can still be inspected
    known = {**FEEDS_AI_CN, **FEEDS}
    articles = fetch_articles({s: known[s] for s in sources})
    fetched = len(articles)
    articles = keyword_filter(filter_recent_articles(articles, hours))
    feed_text = {a.url: a.content for a in articles}
    add_page_content(articles)

    for source in sources:
        selected = [a for a in articles if a.source == source]
        print(f"\n{'=' * 70}\n{source}: {len(selected)} articles in the last {hours} h"
              f" (page fetch: {'yes' if source in PAGE_FETCH_SOURCES else 'no'})")

        for a in selected[:limit]:
            if a.content and a.content != feed_text[a.url]:
                origin = "page"
            elif a.content:
                origin = "feed (full text)"
            else:
                origin = "feed summary only"
            label, text = text_for_scoring(a)
            text = text or ""

            print(f"\n--- {a.title}")
            print(f"Published:   {a.published_at}")
            print(f"URL:         {a.url}")
            print(f"Feed text:   {len(feed_text[a.url] or a.summary or '')} chars, "
                  f"{text_length(feed_text[a.url] or a.summary)} word-eq")
            print(f"Text used:   {origin}, {len(a.content or a.summary or '')} chars, "
                  f"{text_length(a.content or a.summary)} word-eq")
            print(f"To scoring:  {label}, {len(text)} chars, {text_length(text)} word-eq"
                  f" (cap {MAX_CONTENT_WORDS})")
            print(f"Preview:     {text[:preview_chars]}")
            if len(text) > preview_chars:
                print(f"...          {text[-200:]}")

    print(f"\n{fetched} entries fetched, {len(articles)} recent")



if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")   # Chinese text, also when redirected to a file

    # Chinese feeds: text as the pipeline extracts it (feed or page), what
    # scoring receives, and a preview. Adjust hours / limit / preview_chars.
    inspect_extraction(["QbitAI", "Leiphone AI"], hours=24, limit=5, preview_chars=600)

    # FEEDS = {"Electrek": "https://electrek.co/feed/",}
    # inspect_article_webpage("Electrek")
    # inspect_article_webpage("Google DeepMind")

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
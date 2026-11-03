import re
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import time
import trafilatura
from bs4 import BeautifulSoup

from .models import Article
from .textlen import text_length
from .config import (
    FEEDS,
    RECENT_HOURS,
    RECENT_HOURS_OVERRIDES,
    FULL_TEXT_MIN_WORDS,
    MAX_CONTENT_WORDS,
    PAGE_FETCH_SOURCES,
    HTTP_TIMEOUT,
    HTTP_TIMEOUT_OVERRIDES,
    HTTP_RETRIES,
    FEED_KEYWORDS,
    FEED_TIMEZONES,
)


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

    # Pass the raw bytes: trafilatura detects the encoding from the page
    # itself. response.text would use requests' guess, which is ISO-8859-1
    # when the HTTP header names no charset (e.g. Gasgoo), garbling UTF-8.
    return trafilatura.extract(
        response.content,
        include_comments=False,
        include_tables=True
    )


def add_page_content(articles, sources: set[str] | None = None):
    # Only for sources in PAGE_FETCH_SOURCES (or `sources`, for inspection). The page is fetched even when the
    # feed already gave enough text to count as full text (e.g. The Verge's
    # ~150-word opening excerpts), and the longer of the two is kept. If the
    # fetch fails, the feed's text stays. Call after filtering, so old entries
    # are not fetched.
    sources = PAGE_FETCH_SOURCES if sources is None else sources
    for article in articles:
        if article.source not in sources:
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


# A timezone at the end of a feed date: "Z", "+0800", "+08:00", "GMT", "EST"
TIMEZONE_RE = re.compile(r"(Z|[+-]\d{2}:?\d{2}|\b[A-Z]{2,4})\s*$")


def entry_published_at(entry, source: str) -> datetime | None:
    # feedparser gives published_parsed in UTC, and treats a date without a
    # timezone as UTC. For sources in FEED_TIMEZONES, such a date is in
    # that source's local time instead (e.g. Beijing, UTC+8).
    parsed = entry.get("published_parsed")
    if not parsed:
        return None
    published_at = datetime(*parsed[:6], tzinfo=timezone.utc)

    hours = FEED_TIMEZONES.get(source)
    raw = entry.get("published", "")
    if hours is not None and not TIMEZONE_RE.search(raw):
        local = timezone(timedelta(hours=hours))
        published_at = published_at.replace(tzinfo=local).astimezone(timezone.utc)
    return published_at


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

            published_at = entry_published_at(entry, source)

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

def filter_recent_articles(articles, hours: int | None = None):
    # Keep articles published within the lookback window: RECENT_HOURS, or
    # RECENT_HOURS_OVERRIDES for sources whose feeds lag (e.g. Gasgoo).
    # Passing hours applies that one window to every source (for inspection).
    # Undated articles are dropped.
    now = datetime.now(timezone.utc)

    recent_articles = []

    for article in articles:
        if article.published_at is None:
            continue

        window = hours or RECENT_HOURS_OVERRIDES.get(article.source, RECENT_HOURS)
        if article.published_at >= now - timedelta(hours=window):
            recent_articles.append(article)

    return recent_articles


def drop_previously_published(articles, published_urls: set[str]):
    # Articles already published in an earlier run (published_urls, from
    # db.published_urls()) are dropped, so a longer lookback window, a rerun
    # or an off-schedule run never publishes the same article twice.
    # Articles scored but not published earlier stay.
    published = {canonical_url(url) for url in published_urls}
    kept = [a for a in articles if canonical_url(a.url) not in published]
    if len(kept) < len(articles):
        print(f"Already published in an earlier digest: {len(articles) - len(kept)} articles dropped")
    return kept

def canonical_url(url: str) -> str:
    # Drop utm_* tracking parameters; keep everything else, including the
    # #fragment (AI Daily Brief stories differ only by fragment)
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_")]
    return urlunsplit(parts._replace(query=urlencode(query)))


# Shorter normalised titles are too generic to match on ("Weekly roundup")
MIN_TITLE_KEY_CHARS = 10


def title_key(title: str) -> str | None:
    # Lower case, without spaces, punctuation and invisible characters
    # (e.g. zero-width spaces), so trivial differences do not matter.
    # \w keeps letters and digits in any script, including Chinese.
    key = re.sub(r"[\W_]+", "", title.lower())
    return key if len(key) >= MIN_TITLE_KEY_CHARS else None


def deduplicate_articles(articles):
    # The first article wins; a later one is dropped if it has the same
    # canonical URL or the same normalised title. Titles catch the same
    # article under different URLs, e.g. in two Gasgoo category feeds.
    seen_urls = set()
    seen_titles = set()
    unique_articles = []
    dropped_by_title = 0

    for article in articles:
        url = canonical_url(article.url)
        key = title_key(article.title)

        if url in seen_urls:
            continue
        if key and key in seen_titles:
            dropped_by_title += 1
            continue

        seen_urls.add(url)
        if key:
            seen_titles.add(key)
        unique_articles.append(article)

    if dropped_by_title:
        print(f"Deduplicate: {dropped_by_title} articles dropped with the same title as an earlier one")

    return unique_articles


def known_feeds() -> dict[str, str]:
    # FEEDS plus the feed groups that may be on hold (not in FEEDS), so the
    # inspection helpers can check them before they are switched on
    from .config import FEEDS_AI_CN, FEEDS_transport_CN
    return {**FEEDS_AI_CN, **FEEDS_transport_CN, **FEEDS}


def inspect_feed_structure(source: str):
    """
    Inspect the raw RSS fields for one source (FEEDS or an on-hold feed).
    Useful for identifying where article text is stored.
    """
    known = known_feeds()
    if source not in known:
        print(f"Source not found: {source}")
        return

    feed = load_feed(known[source], HTTP_TIMEOUT_OVERRIDES.get(source, HTTP_TIMEOUT))

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



def inspect_extraction(
    sources: list[str],
    hours: int | None = None,
    limit: int = 5,
    preview_chars: int = 600,
    fetch_pages: bool = False,
):
    """Run the pipeline's text steps for the given sources and show the result.

    Same steps as main.py up to scoring: fetch_articles() -> recency filter ->
    keyword_filter() -> add_page_content(), then text_for_scoring(). For each
    article: where the text came from (feed or page), its length in
    characters and word-equivalents (textlen.py), what scoring receives after
    the MAX_CONTENT_WORDS cap, and the start and end of the text. No LLM calls.

    sources: names from FEEDS, FEEDS_AI_CN or FEEDS_transport_CN (on-hold
    feeds can be inspected). hours: one window for all sources (default: each
    source's own, RECENT_HOURS or RECENT_HOURS_OVERRIDES). fetch_pages: also
    fetch article pages for sources not in PAGE_FETCH_SOURCES, to see whether
    adding a source there would help.
    """
    from .scoring import text_for_scoring

    known = known_feeds()
    articles = fetch_articles({s: known[s] for s in sources})
    fetched = len(articles)
    articles = keyword_filter(filter_recent_articles(articles, hours))
    feed_text = {a.url: a.content for a in articles}
    page_sources = PAGE_FETCH_SOURCES | set(sources) if fetch_pages else PAGE_FETCH_SOURCES
    add_page_content(articles, page_sources)

    for source in sources:
        selected = [a for a in articles if a.source == source]
        window = hours or RECENT_HOURS_OVERRIDES.get(source, RECENT_HOURS)
        print(f"\n{'=' * 70}\n{source}: {len(selected)} articles in the last {window} h"
              f" (page fetch: {'yes' if source in page_sources else 'no'}"
              f"{', forced for inspection' if source in page_sources - PAGE_FETCH_SOURCES else ''})")

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

    from .config import FEEDS_transport_CN
    inspect_extraction(list(FEEDS_transport_CN), hours=48, limit=5, preview_chars=600)

    # Other checks (no LLM calls); source names as in config.py:
    # inspect_extraction(["QbitAI", "Leiphone AI"])                 # on-hold Chinese feeds
    # inspect_extraction(["Railway-News"], fetch_pages=True)        # would page fetch help?
    # inspect_feed_structure("Google DeepMind")                     # raw RSS fields

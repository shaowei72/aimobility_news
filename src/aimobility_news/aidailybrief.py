from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from .config import AIDB_SOURCE, RECENT_HOURS
from .models import Article


ARCHIVE_URL = "https://aidailybrief.ai/archive"


def fetch_aidailybrief_stories(hours: int = RECENT_HOURS) -> list[Article]:
    """One Article per story in each recent episode.

    Episodes are split by aidailybrief_transcript.build_stories() (LLM calls,
    cached per episode and model, so reruns cost nothing). Each story is scored
    on its summary and key points. If an episode cannot be split (e.g. its
    transcript is not published yet), the whole edition is kept as one article
    with the archive teaser, as before.
    """
    from .aidailybrief_transcript import build_stories

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    editions = [
        e for e in fetch_aidailybrief_articles()
        if e.published_at and e.published_at >= cutoff
    ]

    articles = []
    for edition in editions:
        date = edition.url.rsplit("/", 1)[-1]
        try:
            result = build_stories(date)
        except Exception as e:
            print(f"WARNING: AI Daily Brief {date} not split into stories, "
                  f"using the whole edition: {type(e).__name__}: {e}")
            articles.append(edition)
            continue

        for story in result["stories"]:
            summary = story["summary"]
            if summary:
                title = summary["headline"]
                text = summary["summary"]
                content = text + "\n\nKey points:\n" + "\n".join(
                    f"- {p}" for p in summary["key_points"]
                )
            else:
                # Summary call failed: score on the raw transcript excerpt
                title, text, content = story["title"], None, story["excerpt"]

            articles.append(Article(
                title=title,
                url=story["url"],
                source=AIDB_SOURCE,
                published_at=edition.published_at,
                summary=text,
                content=content,
            ))

    return articles


def fetch_aidailybrief_articles() -> list[Article]:
    response = requests.get(
        ARCHIVE_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    articles = []
    seen_urls = set()

    for link in soup.find_all("a", class_="ed-title", href=True):

        href = link["href"]

        if not href.startswith("/e/"):
            continue

        # if href.startswith("/e/"):
        #     print("HREF:", href)
        #     print("CLASS:", link.get("class"))
        #     print("TEXT:", link.get_text(" ", strip=True))
        #     print("-" * 50)

        full_url = f"https://aidailybrief.ai{href}"

        # Skip duplicate links to the same edition
        if full_url in seen_urls:
            continue

        title = link.get_text(" ", strip=True)

        # Ignore arrow/icon links
        if not title or title == "→":
            continue

        date_text = href.removeprefix("/e/").strip("/")

        # The URL gives only a date. Stamp it at the end of that day (UTC) so
        # the edition is not treated as up to a day older than it really is.
        try:
            published_at = datetime.strptime(
                date_text,
                "%Y-%m-%d"
            ).replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        except ValueError:
            published_at = None

        # The descriptive paragraph follows the title link
        parent = link.find_parent("div", class_="ed-main")

        summary = None

        if parent:
            teaser = parent.find("div", class_="ed-teaser")

            if teaser:
                summary = teaser.get_text(" ", strip=True)

        article = Article(
            title=title,
            url=full_url,
            source=AIDB_SOURCE,
            published_at=published_at,
            summary=summary,
        )

        articles.append(article)
        seen_urls.add(full_url)

    return articles


if __name__ == "__main__":
    articles = fetch_aidailybrief_articles()

    print(f"Found {len(articles)} AI Daily Brief editions")

    for article in articles[:10]:
        print()
        print(article.title)
        print(article.published_at)
        print(article.url)
        print(article.summary)
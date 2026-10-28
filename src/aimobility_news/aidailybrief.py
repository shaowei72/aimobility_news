from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from .models import Article


ARCHIVE_URL = "https://aidailybrief.ai/archive"


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
            source="AI Daily Brief",
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

import requests
import feedparser
from .config import FEEDS


def validate_feeds():
    for name, url in FEEDS.items():
        print(f"\n{name}")
        print("-" * len(name))

        try:
            response = requests.get(
                url,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/rss+xml, application/xml, */*"
                }
            )

            status = response.status_code
            content_type = response.headers.get("Content-Type", "unknown")

            feed = feedparser.parse(response.content)
            entries = len(feed.entries)

            if status == 200 and entries > 0 and not feed.bozo:
                result = "OK"
            elif status == 200 and entries > 0:
                result = "WARN"
            else:
                result = "FAIL"

            print(f"Result: {result}")
            print(f"HTTP status: {status}")
            print(f"Content type: {content_type}")
            print(f"Parse error: {feed.bozo}")
            print(f"Number of entries: {entries}")

            if feed.bozo:
                print(f"Error details: {feed.bozo_exception}")

            if feed.entries:
                latest = feed.entries[0]
                print(f"Latest title: {latest.get('title', 'No title')}")
                print(f"Published: {latest.get('published', 'No published date')}")
                print(f"Link: {latest.get('link', 'No link')}")

            if status != 200:
                print(f"Response preview: {response.text[:200]}")

        except requests.RequestException as e:
            print("Result: FAIL")
            print(f"HTTP error: {e}")


if __name__ == "__main__":
    validate_feeds()

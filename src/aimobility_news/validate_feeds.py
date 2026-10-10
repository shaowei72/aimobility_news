import feedparser
from .config import FEEDS


def validate_feeds():
    for name, url in FEEDS.items():
        feed = feedparser.parse(url)

        status = getattr(feed, "status", "unknown")
        entries = len(feed.entries)

        if entries > 0 and not feed.bozo:
            result = "OK"
        elif entries > 0:
            result = "WARN"
        else:
            result = "FAIL"

        print(f"\n{name}")
        print("-" * len(name))
        print(f"Result: {result}")
        print(f"HTTP status: {status}")
        print(f"Parse error: {feed.bozo}")
        print(f"Number of entries: {entries}")

        if feed.bozo:
            print(f"Error details: {feed.bozo_exception}")

        if feed.entries:
            latest = feed.entries[0]
            print(f"Latest title: {latest.get('title', 'No title')}")
            print(f"Published: {latest.get('published', 'No published date')}")
            print(f"Link: {latest.get('link', 'No link')}")


if __name__ == "__main__":
    validate_feeds()

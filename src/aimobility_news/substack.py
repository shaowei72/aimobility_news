import requests
import feedparser


def test_substack_feed():
    # url = "https://testimoniumaltus667974.substack.com/feed"
    # url = "https://geoaiunpacked.substack.com/feed"
    url = "https://geospatiallaw.substack.com/feed"

    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20
    )

    print(f"HTTP status: {response.status_code}")

    response.raise_for_status()

    feed = feedparser.parse(response.content)

    print(f"Parse error: {feed.bozo}")
    print(f"Entries: {len(feed.entries)}")

    if feed.bozo:
        print(f"Error: {feed.bozo_exception}")

    for entry in feed.entries[:3]:
        print()
        print(entry.get("title"))
        print(entry.get("published"))
        print(entry.get("link"))


if __name__ == "__main__":
    test_substack_feed()
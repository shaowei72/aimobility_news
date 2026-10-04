import feedparser


feeds = {
    "Esri ArcGIS Blog": "https://www.esri.com/arcgis-blog/feed/",
    "GIM International": "https://www.gim-international.com/rss",
    "ITS International": "https://www.itsinternational.com/rss.xml",
}


for name, url in feeds.items():
    feed = feedparser.parse(url)

    print(f"\n{name}")
    print("-" * len(name))
    print(f"URL: {url}")
    print(f"HTTP status: {getattr(feed, 'status', 'unknown')}")
    print(f"Parse error: {feed.bozo}")
    print(f"Number of entries: {len(feed.entries)}")

    if feed.bozo:
        print(f"Error details: {feed.bozo_exception}")

    if feed.entries:
        latest = feed.entries[0]
        print(f"Latest title: {latest.get('title', 'No title')}")
        print(f"Published: {latest.get('published', 'No published date')}")
        print(f"Link: {latest.get('link', 'No link')}")
    else:
        print("No entries found")

from datetime import datetime, timezone

from openai import OpenAI
from pydantic import BaseModel

from .config import SCORING_MODEL
from .models import Article


class EsriSearchResult(BaseModel):
    title: str
    url: str
    published_at: str | None
    summary: str | None


class EsriSearchResults(BaseModel):
    articles: list[EsriSearchResult]


def fetch_esri_articles() -> list[Article]:
    client = OpenAI()

    prompt = """
Find recent articles from the Esri ArcGIS Blog relevant to:

- GeoAI
- geospatial artificial intelligence
- GIS and AI
- spatial analytics
- mapping and AI
- digital twins
- imagery AI
- AI capabilities in ArcGIS

Only include results from esri.com/arcgis-blog.

Prefer articles published within the last 7 days.
Return at most 10 articles.

For each article return:
- title
- canonical URL
- publication date in ISO 8601 format if available
- a short factual summary
"""

    response = client.responses.parse(
        model=SCORING_MODEL,
        tools=[
            {
                "type": "web_search",
                "filters": {
                    "allowed_domains": [
                        "esri.com"
                    ]
                },
                "search_context_size": "low",
            }
        ],
        input=prompt,
        text_format=EsriSearchResults,
    )

    results = response.output_parsed

    articles = []

    for result in results.articles:
        published_at = None

        if result.published_at:
            try:
                published_at = datetime.fromisoformat(
                    result.published_at.replace("Z", "+00:00")
                )

                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
            
            except ValueError:
                published_at = None

        article = Article(
            title=result.title,
            url=result.url,
            source="Esri ArcGIS Blog",
            published_at=published_at,
            summary=result.summary,
        )

        articles.append(article)

    return articles


if __name__ == "__main__":
    articles = fetch_esri_articles()

    print(f"Found {len(articles)} Esri articles")

    for article in articles:
        print()
        print(article.title)
        print(article.published_at)
        print(article.url)
        print(article.summary)
from .models import Article


def rank_articles(articles: list[Article]) -> list[Article]:
    return sorted(
        articles,
        key=lambda article: article.total_score or 0,
        reverse=True
    )


def select_also_notable(
    articles: list[Article],
    exclude: list[Article],
    limit: int,
    min_transport_score: int,
    min_ai_score: int,
    min_gis_score: int,
) -> list[Article]:
    # Fills a thin digest with articles that are strong in any one domain
    # on its own (transport, AI or GIS at or above its minimum),
    # ranked by transport + AI + GIS.
    if limit <= 0:
        return []

    excluded_urls = {article.url for article in exclude}

    candidates = [
        article
        for article in articles
        if article.url not in excluded_urls
        and (
            (article.transport_score or 0) >= min_transport_score
            or (article.ai_score or 0) >= min_ai_score
            or (article.gis_score or 0) >= min_gis_score
        )
    ]

    candidates.sort(
        key=lambda article: (article.transport_score or 0)
        + (article.ai_score or 0)
        + (article.gis_score or 0),
        reverse=True
    )

    return candidates[:limit]

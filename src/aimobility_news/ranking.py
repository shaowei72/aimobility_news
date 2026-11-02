from .config import (
    MIN_TOTAL_SCORE,
    NOTABLE_MIN_TRANSPORT_SCORE,
    NOTABLE_MIN_AI_SCORE,
    NOTABLE_MIN_GIS_SCORE,
)
from .models import Article


QUALIFIED = "qualified"
NOTABLE = "notable"
BELOW_THRESHOLD = "below threshold"
SCORING_FAILED = "scoring failed"


def rank_articles(articles: list[Article]) -> list[Article]:
    return sorted(
        articles,
        key=lambda article: article.total_score or 0,
        reverse=True
    )


def classify_article(article: Article) -> str:
    # qualified: total_score reaches MIN_TOTAL_SCORE
    # notable:   otherwise, any one domain reaches its NOTABLE_MIN_* score
    # below threshold: everything else
    # scoring failed: no scores (never published)
    if article.scoring_error:
        return SCORING_FAILED

    if (article.total_score or 0) >= MIN_TOTAL_SCORE:
        return QUALIFIED

    if (
        (article.transport_score or 0) >= NOTABLE_MIN_TRANSPORT_SCORE
        or (article.ai_score or 0) >= NOTABLE_MIN_AI_SCORE
        or (article.gis_score or 0) >= NOTABLE_MIN_GIS_SCORE
    ):
        return NOTABLE

    return BELOW_THRESHOLD


def classify_articles(articles: list[Article]) -> list[Article]:
    for article in articles:
        article.digest_status = classify_article(article)
    return articles


def select_for_digest(
    ranked_articles: list[Article],
    limit: int,
) -> list[Article]:
    # Qualified and notable articles, highest total first, up to limit.
    # Notable articles always score below MIN_TOTAL_SCORE, so in ranked
    # order every qualified article comes before every notable one.
    published = [
        article
        for article in ranked_articles
        if article.digest_status in (QUALIFIED, NOTABLE)
    ][:limit]

    for article in published:
        article.published = True

    return published

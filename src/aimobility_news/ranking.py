from .config import (
    MIN_TOTAL_SCORE,
    NOTABLE_MIN_TRANSPORT_SCORE,
    NOTABLE_MIN_AI_SCORE,
    NOTABLE_MIN_GIS_SCORE,
    AIDB_SOURCE,
    AIDB_HEADLINES_MIN_AI_SCORE,
)
from .models import Article, ROUNDUP


QUALIFIED = "qualified"
NOTABLE = "notable"
AI_HEADLINE = "ai headline"
BELOW_THRESHOLD = "below threshold"
SCORING_FAILED = "scoring failed"


def rank_articles(articles: list[Article]) -> list[Article]:
    return sorted(
        articles,
        key=lambda article: article.total_score or 0,
        reverse=True
    )


def classify_article(article: Article) -> str:
    # qualified: total_score reaches MIN_TOTAL_SCORE, and the article is not
    #            a roundup (roundups score across many topics without one
    #            substantial story, so at most they are notable)
    # ai headline: otherwise, an AI Daily Brief story whose AI score reaches
    #            AIDB_HEADLINES_MIN_AI_SCORE (own digest section, own cap)
    # notable:   otherwise, any one domain reaches its NOTABLE_MIN_* score
    # below threshold: everything else
    # scoring failed: no scores (never published)
    if article.scoring_error:
        return SCORING_FAILED

    if (
        (article.total_score or 0) >= MIN_TOTAL_SCORE
        and article.article_type != ROUNDUP
    ):
        return QUALIFIED

    if (
        article.source == AIDB_SOURCE
        and (article.ai_score or 0) >= AIDB_HEADLINES_MIN_AI_SCORE
    ):
        return AI_HEADLINE

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


def digest_order(ranked_articles: list[Article]) -> list[Article]:
    # Qualified articles, then notable ones with roundups last, each group
    # highest total first. Grouped explicitly because a roundup can be
    # notable with a total above MIN_TOTAL_SCORE.
    qualified = [a for a in ranked_articles if a.digest_status == QUALIFIED]
    notable = [a for a in ranked_articles if a.digest_status == NOTABLE]
    # sorted() is stable, so the order within each group is kept
    return qualified + sorted(notable, key=lambda a: a.article_type == ROUNDUP)


def select_for_digest(
    ranked_articles: list[Article],
    limit: int,
) -> list[Article]:
    # The first `limit` articles in digest_order()
    published = digest_order(ranked_articles)[:limit]

    for article in published:
        article.published = True

    return published


def select_ai_headlines(
    ranked_articles: list[Article],
    limit: int,
) -> list[Article]:
    # AI headlines (AI Daily Brief stories that did not qualify), highest AI
    # score first, then total, up to limit. Separate from select_for_digest()
    # so they never take a main digest slot.
    headlines = sorted(
        (a for a in ranked_articles if a.digest_status == AI_HEADLINE),
        key=lambda a: (a.ai_score or 0, a.total_score or 0),
        reverse=True,
    )[:limit]

    for article in headlines:
        article.published = True

    return headlines

from .models import Article


def rank_articles(articles: list[Article]) -> list[Article]:
    return sorted(
        articles,
        key=lambda article: article.total_score or 0,
        reverse=True
    )
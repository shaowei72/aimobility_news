from .feeds import (
    fetch_articles,
    filter_recent_articles,
    deduplicate_articles,
)
from .scoring import score_articles
from .ranking import rank_articles
from .digest import generate_digest, save_digest
from .esri_search import fetch_esri_articles
from .aidailybrief import fetch_aidailybrief_articles
from .config import TOP_RANKED, MIN_TOTAL_SCORE


def main():
    rss_articles = fetch_articles()
    esri_articles = fetch_esri_articles()
    aidailybrief_articles = fetch_aidailybrief_articles()
    
    print(f"RSS articles: {len(rss_articles)}")
    print(f"Esri articles: {len(esri_articles)}")
    print(f"AIDailybrief articles: {len(aidailybrief_articles)}")

    # for article in esri_articles:
    #     print(
    #         article.title,
    #         "|",
    #         article.published_at
    #     )

    articles = rss_articles + esri_articles + aidailybrief_articles
    print(f"Combined articles: {len(articles)}")

    recent_articles = filter_recent_articles(articles)
    print(f"Recent articles: {len(recent_articles)}")

    for article in recent_articles:
        print(article.source, "|", article.published_at, "|", article.title)

    unique_articles = deduplicate_articles(recent_articles)
    scored_articles = score_articles(unique_articles)
    ranked_articles = rank_articles(scored_articles)

    qualified_articles = [
        article
        for article in ranked_articles
        if article.total_score >= MIN_TOTAL_SCORE
    ]

    top_N = qualified_articles[:TOP_RANKED]

    digest = generate_digest(top_N)
    file_path = save_digest(digest)

    print(f"Digest saved to: {file_path}")


if __name__ == "__main__":
    main()
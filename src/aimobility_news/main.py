from .feeds import (
    fetch_articles,
    filter_recent_articles,
    deduplicate_articles,
)
from .scoring import score_articles
from .ranking import rank_articles
from .digest import generate_digest, save_digest


def main():
    articles = fetch_articles()
    recent_articles = filter_recent_articles(articles)
    unique_articles = deduplicate_articles(recent_articles)
    scored_articles = score_articles(unique_articles)
    ranked_articles = rank_articles(scored_articles)

    top_5 = ranked_articles[:5]

    digest = generate_digest(top_5)
    file_path = save_digest(digest)

    print(f"Digest saved to: {file_path}")


if __name__ == "__main__":
    main()
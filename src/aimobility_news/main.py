import time
from contextlib import contextmanager

from .feeds import (
    fetch_articles,
    filter_recent_articles,
    deduplicate_articles,
    add_page_content,
)
from .scoring import score_articles
from .ranking import rank_articles, select_also_notable
from .digest import generate_digest, generate_debug_digest, save_digest
from .esri_search import fetch_esri_articles
from .aidailybrief import fetch_aidailybrief_articles
from .config import (
    TOP_RANKED,
    MIN_TOTAL_SCORE,
    NOTABLE_MIN_TRANSPORT_SCORE,
    NOTABLE_MIN_AI_SCORE,
    NOTABLE_MIN_GIS_SCORE,
)


timings = {}


@contextmanager
def timed(step):
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    timings[step] = elapsed
    print(f"[{step}] {elapsed:.1f}s")


def print_timing_summary(total):
    print("\n--- Timing summary ---")
    for step, secs in sorted(timings.items(), key=lambda x: -x[1]):
        print(f"{step:<35} {secs:6.1f}s  {secs / total:5.0%}")
    print(f"{'Total':<35} {total:6.1f}s")


def main():
    timings.clear()
    total_start = time.perf_counter()

    with timed("Fetch RSS"):
        rss_articles = fetch_articles()
    with timed("Fetch Esri"):
        esri_articles = fetch_esri_articles()
    with timed("Fetch AI Daily Brief"):
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

    with timed("Filter recent"):
        recent_articles = filter_recent_articles(articles)
    print(f"Recent articles: {len(recent_articles)}")

    # for article in recent_articles:
    #     print(article.source, "|", article.published_at, "|", article.title)

    with timed("Deduplicate"):
        unique_articles = deduplicate_articles(recent_articles)

    with timed("Fetch article pages"):
        unique_articles = add_page_content(unique_articles)

    with timed(f"Score ({len(unique_articles)} articles)"):
        scored_articles = score_articles(unique_articles)

    with timed("Rank + threshold"):
        ranked_articles = rank_articles(scored_articles)

        qualified_articles = [
            article
            for article in ranked_articles
            if article.total_score >= MIN_TOTAL_SCORE
        ]

        top_N = qualified_articles[:TOP_RANKED]

        also_notable = select_also_notable(
            ranked_articles,
            exclude=top_N,
            limit=TOP_RANKED - len(top_N),
            min_transport_score=NOTABLE_MIN_TRANSPORT_SCORE,
            min_ai_score=NOTABLE_MIN_AI_SCORE,
            min_gis_score=NOTABLE_MIN_GIS_SCORE,
        )

    print(f"Qualified: {len(top_N)}, also notable: {len(also_notable)}")

    with timed(f"Generate digest ({len(top_N) + len(also_notable)} items)"):
        digest = generate_digest(top_N, also_notable)

    with timed("Save"):
        file_path = save_digest(digest)

        debug_digest = generate_debug_digest(
            ranked_articles, top_N, also_notable, MIN_TOTAL_SCORE
        )
        debug_file_path = save_digest(debug_digest, prefix="debug-digest")

    print(f"Digest saved to: {file_path}")
    print(f"Debug digest saved to: {debug_file_path}")

    print_timing_summary(time.perf_counter() - total_start)


if __name__ == "__main__":
    main()

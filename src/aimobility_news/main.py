import argparse
import time
from contextlib import contextmanager

from .feeds import (
    fetch_articles,
    filter_recent_articles,
    deduplicate_articles,
    drop_previously_published,
    keyword_filter,
    add_page_content,
)
from . import llm
from .scoring import score_articles
from .ranking import (
    rank_articles,
    classify_articles,
    select_for_digest,
    select_ai_headlines,
)
from .digest import generate_digest, generate_debug_digest, save_digest
from .digest_whatsapp import build_whatsapp, copy_to_clipboard
from . import db
from .esri_search import fetch_esri_articles
from .aidailybrief import fetch_aidailybrief_stories
from .config import TOP_RANKED, MIN_TOTAL_SCORE, AIDB_HEADLINES_MAX, WHATSAPP_COPY_TO_CLIPBOARD


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


def main(provider: str | None = None):
    if provider:
        llm.set_provider(provider)

    print(
        f"LLM provider: {llm.get_provider()} "
        f"(scoring {llm.model_for('scoring')}, digest {llm.model_for('digest')})"
    )

    timings.clear()
    total_start = time.perf_counter()

    with timed("Fetch RSS"):
        rss_articles = fetch_articles()
    with timed("Fetch Esri"):
        # Esri discovery always uses OpenAI web search, whatever the provider.
        # A failure here (e.g. no OPENAI_API_KEY on a local-only run) skips
        # Esri instead of aborting the run.
        try:
            esri_articles = fetch_esri_articles()
        except Exception as e:
            print(f"WARNING: Esri search skipped: {e}")
            esri_articles = []
    with timed("Fetch AI Daily Brief"):
        # Recent episodes split into stories (LLM, task "transcript"; cached
        # per episode). A failure skips the source instead of aborting the run.
        try:
            aidailybrief_articles = fetch_aidailybrief_stories()
        except Exception as e:
            print(f"WARNING: AI Daily Brief skipped: {type(e).__name__}: {e}")
            aidailybrief_articles = []

    print(f"RSS articles: {len(rss_articles)}")
    print(f"Esri articles: {len(esri_articles)}")
    print(f"AI Daily Brief stories: {len(aidailybrief_articles)}")

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

        # Never publish an article twice (longer lookback windows, reruns).
        # A database problem only warns: the run continues without the check.
        try:
            with db.session() as conn:
                already_published = db.published_urls(conn)
            unique_articles = drop_previously_published(unique_articles, already_published)
        except Exception as e:
            print(f"WARNING: could not check earlier digests: {type(e).__name__}: {e}")

    with timed("Keyword filter"):
        # Only sources listed in FEED_KEYWORDS (none by default)
        unique_articles = keyword_filter(unique_articles)

    with timed("Fetch article pages"):
        unique_articles = add_page_content(unique_articles)

    with timed(f"Score ({len(unique_articles)} articles)"):
        # Articles whose identical prompt the same model has already scored
        # (e.g. on an earlier run today) reuse the stored score
        with db.session() as conn:
            to_score = db.reuse_scores(conn, unique_articles)
        print(f"Scores reused from the database: {len(unique_articles) - len(to_score)}, "
              f"to score: {len(to_score)}")
        score_articles(to_score)
        scored_articles = unique_articles

    with timed("Rank + classify"):
        ranked_articles = classify_articles(rank_articles(scored_articles))
        published = select_for_digest(ranked_articles, limit=TOP_RANKED)
        ai_headlines = select_ai_headlines(ranked_articles, limit=AIDB_HEADLINES_MAX)

    statuses = [article.digest_status for article in ranked_articles]
    print(
        f"Qualified: {statuses.count('qualified')}, "
        f"notable: {statuses.count('notable')}, "
        f"AI headlines: {statuses.count('ai headline')}, "
        f"scoring failed: {statuses.count('scoring failed')}, "
        f"published: {len(published)} + {len(ai_headlines)} AI headlines"
    )

    with timed(f"Generate digest ({len(published)} items)"):
        # Reuse of stored summaries is disabled (see db.reuse_summaries()):
        # with db.session() as conn:
        #     db.reuse_summaries(conn, published)
        digest = generate_digest(ranked_articles, ai_headlines)

    # Before the database save, so the one-liners are stored with the
    # summaries. A failure here only warns; the Markdown digest is unaffected.
    with timed("WhatsApp text"):
        try:
            whatsapp = build_whatsapp(ranked_articles, ai_headlines)
            whatsapp_path = save_digest(whatsapp, prefix="whatsapp", suffix=".txt")
            whatsapp_message = f"WhatsApp text saved to: {whatsapp_path}"
            if WHATSAPP_COPY_TO_CLIPBOARD and copy_to_clipboard(whatsapp):
                whatsapp_message += " (copied to the clipboard: paste into WhatsApp)"
        except Exception as e:
            whatsapp_message = f"WARNING: WhatsApp text failed: {type(e).__name__}: {e}"

    with timed("Save"):
        file_path = save_digest(digest)

        debug_digest = generate_debug_digest(ranked_articles, MIN_TOTAL_SCORE)
        debug_file_path = save_digest(debug_digest, prefix="debug-digest")

        # The digests are already saved, so a database problem only warns
        try:
            with db.session() as conn:
                run_id = db.start_run(conn, "pipeline")
                db.save_articles(conn, run_id, ranked_articles)
            db_message = f"{len(ranked_articles)} articles saved to {db.DB_PATH}"
        except Exception as e:
            db_message = f"WARNING: could not save to the database: {type(e).__name__}: {e}"

    print(f"Digest saved to: {file_path}")
    print(f"Debug digest saved to: {debug_file_path}")
    print(whatsapp_message)
    print(db_message)

    print_timing_summary(time.perf_counter() - total_start)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the daily digest")
    parser.add_argument(
        "--provider",
        choices=llm.PROVIDERS,
        help="LLM provider for scoring and digest (default: LLM_PROVIDER in config.py)",
    )
    args = parser.parse_args()

    main(provider=args.provider)

"""Backfill AI Daily Brief episodes into the database (v0.4).

For each episode on the archive page in the date range:
1. split it into stories (aidailybrief_transcript.build_stories(); story sets
   already in the database for the current transcript model are reused)
2. score each story with the scoring model (scores already in the database
   for an identical prompt are reused)
3. classify each story (qualified / ai headline / notable / ...) and store
   articles, scores and statuses (digest_items, published = 0)

Each episode is committed on its own, so an interrupted backfill resumes
where it stopped when run again, without repeating LLM calls.

Usage:
    uv run python -m aimobility_news.backfill_aidb --since 2026-08-03
    uv run python -m aimobility_news.backfill_aidb --since 2026-08-03 --until 2026-08-16
    uv run python -m aimobility_news.backfill_aidb --since 2026-08-03 --dry-run
"""

import argparse
import time
from datetime import date as Date

from . import db, llm
from .aidailybrief import fetch_aidailybrief_articles, story_articles
from .aidailybrief_transcript import build_stories
from .ranking import classify_articles
from .scoring import score_articles


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill AI Daily Brief episodes into the database")
    parser.add_argument("--since", required=True, help="first episode date, YYYY-MM-DD")
    parser.add_argument("--until", default=Date.today().isoformat(), help="last episode date (default today)")
    parser.add_argument("--provider", choices=llm.PROVIDERS, help="LLM provider (default LLM_PROVIDER)")
    parser.add_argument("--dry-run", action="store_true", help="list the episodes and what is already stored; no LLM calls")
    args = parser.parse_args()

    if args.provider:
        llm.set_provider(args.provider)

    editions = sorted(
        (e for e in fetch_aidailybrief_articles()
         if args.since <= e.url.rsplit("/", 1)[-1] <= args.until),
        key=lambda e: e.url,
    )
    model = llm.describe("transcript")
    print(f"{len(editions)} episodes from {args.since} to {args.until}")
    print(f"Stories: {model}; scoring: {llm.describe('scoring')}")

    if args.dry_run:
        with db.session() as conn:
            for e in editions:
                date = e.url.rsplit("/", 1)[-1]
                stored = db.load_story_set(conn, date, model)
                print(f"  {date}  {'stories stored' if stored else 'to split':<15} {e.title}")
        return

    totals = {"episodes": 0, "failed": 0, "stories": 0, "scored": 0, "reused": 0, "score_errors": 0}
    start = time.perf_counter()

    with db.session() as conn:
        run_id = db.start_run(conn, "backfill aidb")

    for n, edition in enumerate(editions, 1):
        date = edition.url.rsplit("/", 1)[-1]
        print(f"\n[{n}/{len(editions)}] {date}  {edition.title}")
        try:
            result = build_stories(date)
            articles = story_articles(result, edition.published_at)

            with db.session() as conn:
                to_score = db.reuse_scores(conn, articles)
            if to_score:
                try:
                    score_articles(to_score)
                except RuntimeError as e:
                    # Every story in this episode failed; keep the failures, go on
                    print(f"  WARNING: {e}")

            classify_articles(articles)
            with db.session() as conn:
                db.save_articles(conn, run_id, articles)

            errors = sum(1 for a in articles if a.scoring_error)
            totals["episodes"] += 1
            totals["stories"] += len(articles)
            totals["scored"] += len(to_score) - errors
            totals["reused"] += len(articles) - len(to_score)
            totals["score_errors"] += errors
            for a in articles:
                print(f"  {a.digest_status:<16} T{a.transport_score} A{a.ai_score} G{a.gis_score}  {a.title[:80]}")
        except Exception as e:
            totals["failed"] += 1
            print(f"  ERROR: {type(e).__name__}: {e}")

    minutes = (time.perf_counter() - start) / 60
    print(
        f"\nDone in {minutes:.1f} min: {totals['episodes']} episodes ({totals['failed']} failed), "
        f"{totals['stories']} stories; {totals['scored']} scored, {totals['reused']} reused, "
        f"{totals['score_errors']} scoring errors. Run id: {run_id}"
    )


if __name__ == "__main__":
    main()

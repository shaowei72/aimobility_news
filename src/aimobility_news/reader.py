"""Digest reader: write stored digest content to one Markdown file.

Entries are grouped by day, newest first. Each goes under the day its
content came out:

    its    ITS articles: the article's published date (local time), from
           digest_items, articles, scores and summaries. An article
           published in several runs appears once, from the latest run.
    aidb   AI Daily Brief episodes and their stories: the episode date,
           from aidb_story_sets.

With no section named, both are mixed day by day (ITS first within a day,
as in the digest); --since/--until filter on these content dates.

Standalone: imports from the package .web.queries, so must be run with -m; and the
database is opened read-only, so it is safe to run while a backfill or the
pipeline is writing to it.

    uv run python -m aimobility_news.reader                             # both, last 7 days
    uv run python -m aimobility_news.reader --since 2026-10-01
    uv run python -m aimobility_news.reader aidb --min-ai-score 4       # AI Daily Brief only
    uv run python -m aimobility_news.reader its --all                   # every scored ITS article, with reasons

Output goes to output/reader/<section or all>-<since>_<until>.md unless
--out is given. Open it in VS Code's Markdown preview (Ctrl+Shift+V); the
Outline view lists the days and entries.
"""
import argparse
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from .web.queries import connect_read_only, local_day, load_its_rows, load_episodes, story_urls, ai_score, DEFAULT_DB


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = PROJECT_ROOT / "output" / "reader"
DEFAULT_DAYS = 7

# One entry is (day "YYYY-MM-DD", markdown lines, number of items it holds)
Entry = tuple[str, list[str], int]


# ------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------


def clock(hhmmss: str | None) -> str:
    # "00:27:00" -> "27:00", "01:02:03" stays
    if not hhmmss:
        return "?"
    return hhmmss[3:] if hhmmss.startswith("00:") else hhmmss


def score_line(row) -> str:
    if row["total_score"] is None:
        return "not scored"
    return (f"{row['total_score']} (Transport {row['transport_score']}, "
            f"AI {row['ai_score']}, GIS {row['gis_score']})")


# ------------------------------------------------------------
# ITS: articles by published date
# ------------------------------------------------------------

def render_its_article(row, include_all: bool) -> list[str]:
    lines = [f"### ITS · {row['title']}", ""]
    if row["title_en"] and row["title_en"] != row["title"]:
        lines += [f"_{row['title_en']}_", ""]

    status = row["digest_status"] + (", published" if row["published"] else "")
    lines.append(f"**Source:** {row['source']} · **In digest:** {row['run_id'][:16]}")
    lines.append(f"**Score:** {score_line(row)} · **Status:** {status}")
    lines.append("")

    if row["summary"]:
        lines += [row["summary"], "", f"**Why it matters:** {row['why_it_matters']}", ""]
    elif row["summary_error"]:
        lines += [f"_Summary failed: {row['summary_error']}_", ""]
    elif row["published"]:
        lines += ["_No stored summary (published before summaries were saved)._", ""]

    if include_all:
        if row["scoring_error"]:
            lines += [f"**Scoring error:** {row['scoring_error']}", ""]
        for field, label in (("transport", "Transport"), ("ai", "AI"), ("gis", "GIS")):
            reason = row[f"{field}_reason"]
            if reason:
                lines += [f"**{label} reason:** {reason}", ""]

    lines += [f"[Read article]({row['url']})", ""]
    return lines


def its_entries(conn: sqlite3.Connection, args) -> list[Entry]:
    entries = []
    for row in load_its_rows(conn, args.all):
        # Undated articles go under the day of the run that published them
        day = local_day(row["published_at"]) or row["run_id"][:10]
        if args.since <= day <= args.until:
            entries.append((row, day))

    # Within a day: published first, then highest score
    entries.sort(key=lambda e: (not e[0]["published"], -(e[0]["total_score"] or 0)))
    return [(day, render_its_article(row, args.all), 1) for row, day in entries]


# ------------------------------------------------------------
# AI Daily Brief: episodes and stories by episode date
# ------------------------------------------------------------
def render_episode(ep: dict, shown: list[tuple], n_stories: int) -> list[str]:
    result = ep["result"]
    lines = [f"### AI Daily Brief · {ep['title'] or result.get('episode_title', '')}", ""]
    if ep["lead"]:
        lines += [f"_{ep['lead']}_", ""]
    lines += [f"[Episode]({ep['url']}) · {len(shown)} of {n_stories} stories · "
              f"by {ep['model']}", ""]

    for i, (story, url, score) in enumerate(shown, start=1):
        summary = story.get("summary")
        headline = summary["headline"] if summary else story["title"]
        window = story.get("window") or {}
        score_text = f"AI score {score}/5" if score is not None else "not scored"

        lines += [f"#### {i}. {headline}", ""]
        lines += [f"**{score_text}** · {story.get('section', '')} · "
                  f"{clock(window.get('start'))}–{clock(window.get('end'))} · "
                  f"[Listen / read]({url})", ""]
        if summary:
            lines += [summary["summary"], ""]
            lines += [f"- {point}" for point in summary.get("key_points", [])]
            lines.append("")
        else:
            lines += [f"_Summary unavailable ({story.get('summary_error') or 'no summary'})._", ""]
    return lines


def aidb_entries(conn: sqlite3.Connection, args) -> list[Entry]:
    entries = []
    for ep in load_episodes(conn, args.since, args.until, args.model):
        stories = ep["result"].get("stories", [])
        shown = []
        for story, url in zip(stories, story_urls(stories)):
            score = ai_score(conn, url, ep["model"])
            if args.min_ai_score is not None and (score is None or score < args.min_ai_score):
                continue
            shown.append((story, url, score))
        if shown:
            entries.append((ep["date"], render_episode(ep, shown, len(stories)), len(shown)))
    return entries


# ------------------------------------------------------------
# Command line
# ------------------------------------------------------------

SECTIONS = {
    # section: (entries function, title, unit name for the printed counts),
    # in digest order (the order within a day)
    "its": (its_entries, "ITS articles", "articles"),
    "aidb": (aidb_entries, "AI Daily Brief", "stories"),
}


def valid_date(text: str) -> str:
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a YYYY-MM-DD date: {text!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write stored digest content to a Markdown file, by day")
    parser.add_argument("section", nargs="?", choices=SECTIONS,
                        help="its: ITS articles only; aidb: AI Daily Brief only (default: both)")
    parser.add_argument("--since", type=valid_date, help=f"first date (default: {DEFAULT_DAYS} days before --until)")
    parser.add_argument("--until", type=valid_date, help="last date (default: today)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"database file (default: {DEFAULT_DB})")
    parser.add_argument("--out", type=Path, help="output file (default: output/reader/<section or all>-<since>_<until>.md)")

    aidb = parser.add_argument_group("aidb options")
    aidb.add_argument("--min-ai-score", type=int, help="only stories with at least this AI score (0-5)")
    aidb.add_argument("--model", default="openai",
                      help="preferred story-set model prefix when an episode has several (default: openai)")

    its = parser.add_argument_group("its options")
    its.add_argument("--all", action="store_true",
                     help="every scored ITS article, not just published ones, with scoring reasons")
    args = parser.parse_args()

    args.until = args.until or date.today().isoformat()
    args.since = args.since or (date.fromisoformat(args.until) - timedelta(days=DEFAULT_DAYS)).isoformat()
    if args.since > args.until:
        parser.error("--since is after --until")

    sections = [args.section] if args.section else list(SECTIONS)

    # Collect every section's entries, then group by day, newest first.
    # The sort is stable, so within a day the section order and each
    # section's own order are kept.
    entries, counts = [], []
    conn = connect_read_only(args.db)
    try:
        for section in sections:
            make_entries, title, unit = SECTIONS[section]
            section_entries = make_entries(conn, args)
            entries += section_entries
            counts.append(f"{title}: {sum(n for _, _, n in section_entries)} {unit}")
    finally:
        conn.close()
    entries.sort(key=lambda e: e[0], reverse=True)

    title = SECTIONS[args.section][1] if args.section else "Digest history"
    lines = [f"# {title} — {args.since} to {args.until}", ""]
    if not entries:
        lines += ["_Nothing in the database for these dates._", ""]

    day = None
    for entry_day, entry_lines, _ in entries:
        if entry_day != day:
            if day is not None:
                lines += ["---", ""]
            day = entry_day
            lines += [f"## {day}", ""]
        lines += entry_lines

    name = args.section or "all"
    out = args.out or DEFAULT_OUT_DIR / f"{name}-{args.since}_{args.until}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    n_days = len({e[0] for e in entries})
    print(f"{n_days} days, " + ", ".join(counts))
    print(f"-> {out}")


if __name__ == "__main__":
    main()

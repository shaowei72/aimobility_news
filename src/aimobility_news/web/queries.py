"""Read-only queries on the news database, shared by reader.py and the web app.

One definition of the rules both need (spec section 3.2):
- the database is opened read-only, never through db.connect();
- the "content day" of an item is in local time;
- when an article appears in several pipeline runs, the latest run wins;
- an AI Daily Brief episode uses its preferred story-set model (openai first);
- story URLs are built as aidailybrief.story_articles() builds them.

Standard library only, and no imports from the rest of the package, so the
reader stays standalone (spec decision 5).
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

# ------------------------------------------------------------
# Locations and constants
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = PROJECT_ROOT / "output" / "db" / "news.db"     # config.DB_FILE
AIDB_SOURCE = "AI Daily Brief"                               # aidailybrief.AIDB_SOURCE


# ------------------------------------------------------------
# Connection and dates
# ------------------------------------------------------------

def connect_read_only(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise SystemExit(f"Database not found: {path}")
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def local_day(iso: str | None) -> str | None:
    # Stored timestamps are ISO 8601 UTC; the day is in local time
    if not iso:
        return None
    dt = datetime.fromisoformat(iso)
    return (dt.astimezone() if dt.tzinfo else dt).date().isoformat()


# ------------------------------------------------------------
# ITS articles
# ------------------------------------------------------------

def load_its_rows(conn: sqlite3.Connection, include_all: bool) -> list[sqlite3.Row]:
    """ITS articles of pipeline runs, one row per article from its latest
    run. Only published articles unless include_all."""
    published_only = "" if include_all else "AND d.published = 1"
    rows = conn.execute(
        f"""
        SELECT d.run_id, d.digest_status, d.published,
               a.title, a.url, a.source, a.published_at,
               s.scored_by, s.total_score, s.transport_score, s.ai_score, s.gis_score,
               s.transport_reason, s.ai_reason, s.gis_reason, s.error AS scoring_error,
               m.title_en, m.summary, m.why_it_matters, m.error AS summary_error
        FROM digest_items d
        JOIN runs r       ON r.run_id = d.run_id
        JOIN articles a   ON a.id = d.article_id
        LEFT JOIN scores s    ON s.id = d.score_id
        LEFT JOIN summaries m ON m.id = d.summary_id
        WHERE r.kind LIKE 'pipeline%' AND a.source <> ? {published_only}
        ORDER BY d.run_id DESC
        """,
        (AIDB_SOURCE,),
    ).fetchall()

    latest, seen = [], set()
    for row in rows:
        if row["url"] not in seen:
            seen.add(row["url"])
            latest.append(row)
    return latest

# ------------------------------------------------------------
# AI Daily Brief
# ------------------------------------------------------------

def load_episodes(conn: sqlite3.Connection, since: str, until: str, model: str) -> list[dict]:
    """One story set per episode. Prefers a set whose model starts with
    `model` (e.g. "openai"), otherwise the most recently saved."""
    rows = conn.execute(
        """
        SELECT e.date, e.url, e.title, e.lead, s.model, s.saved_at, s.result
        FROM aidb_episodes e JOIN aidb_story_sets s ON s.episode_date = e.date
        WHERE e.date BETWEEN ? AND ?
        ORDER BY e.date DESC, (s.model LIKE ? || '%') DESC, s.saved_at DESC
        """,
        (since, until, model),
    ).fetchall()

    episodes, seen = [], set()
    for row in rows:
        if row["date"] in seen:
            continue
        seen.add(row["date"])
        episodes.append({**dict(row), "result": json.loads(row["result"])})
    return episodes


def story_urls(stories: list[dict]) -> list[str]:
    # Same rule as aidailybrief.story_articles(), so the URLs match the
    # articles (and their scores) in the database
    urls, seen = [], set()
    for story in stories:
        url = story["url"]
        if "#" not in url or url in seen:
            url = f"{url.split('#')[0]}#{story['id']}"
        seen.add(url)
        urls.append(url)
    return urls


def ai_score(conn: sqlite3.Connection, url: str, model: str) -> int | None:
    # Latest successful score, preferring the model that wrote the story set
    row = conn.execute(
        """
        SELECT s.ai_score FROM scores s JOIN articles a ON a.id = s.article_id
        WHERE a.url = ? AND s.error IS NULL
        ORDER BY (s.scored_by = ?) DESC, s.id DESC LIMIT 1
        """,
        (url, model),
    ).fetchone()
    return row["ai_score"] if row else None

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
if __name__ == "__main__":
    print("Web query interface")

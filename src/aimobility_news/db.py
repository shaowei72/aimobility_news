"""SQLite news repository (v0.4).

One database file (DB_FILE, default output/db/news.db) holds:

    runs            one row per pipeline, backfill or import run
    articles        one row per URL (RSS articles, Esri posts, AI Daily Brief
                    stories), with the latest title, summary and longest text
    scores          every scoring of an article: who scored it, a hash of the
                    exact prompt, the text the model saw, scores and reasons.
                    Several rows per article (re-scores, other models).
    summaries       every digest summary of a published ITS article: model,
                    a hash of the exact prompt, title_en, summary, why it
                    matters, error, and the WhatsApp one-liner (v0.5)
    digest_items    per run and article: digest status, published, section,
                    and the score and summary used
    aidb_episodes   AI Daily Brief episodes (date, title, lead)
    aidb_story_sets one story split of one episode by one model: the full
                    build_stories() result as JSON (headings, groupings,
                    excerpts, summaries)

Scores are reused: if the same model has already scored an identical prompt
(same rubric, title and text; see scoring.scoring_prompt()), the stored score
is applied instead of calling the LLM again. This makes reruns and the
AI Daily Brief backfill cheap and resumable. Summaries are stored but not
reused (only same-day re-runs would benefit); see reuse_summaries().

Command line:
    uv run python -m aimobility_news.db --import-legacy   # JSONL pool + story JSON files
    uv run python -m aimobility_news.db --stats
"""

import argparse
import hashlib
import json
import sqlite3
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import llm
from .config import DB_FILE, AIDB_DIR, MIN_TOTAL_SCORE, MAX_CONTENT_WORDS, RECENT_HOURS
from .models import Article
from .ranking import AI_HEADLINE


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / DB_FILE

# Digest sections, as stored in digest_items.section
SECTION_ITS = "its"
SECTION_AIDB = "ai daily brief"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id        TEXT PRIMARY KEY,      -- llm.RUN_ID, "YYYY-MM-DD HH:MM:SS" (local time)
    kind          TEXT NOT NULL,         -- "pipeline", "backfill aidb", "import"
    started_at    TEXT NOT NULL,         -- ISO 8601, UTC
    code_version  TEXT,                  -- short git commit, "+dirty" if uncommitted changes
    settings      TEXT                   -- JSON: provider, models, thresholds
);

CREATE TABLE IF NOT EXISTS articles (
    id             INTEGER PRIMARY KEY,
    url            TEXT NOT NULL UNIQUE,
    title          TEXT NOT NULL,
    source         TEXT NOT NULL,
    published_at   TEXT,                 -- ISO 8601, UTC
    summary        TEXT,
    content        TEXT,                 -- longest full text seen
    first_seen_run TEXT,
    first_seen_at  TEXT NOT NULL,
    last_seen_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS articles_source ON articles(source, published_at);

CREATE TABLE IF NOT EXISTS scores (
    id               INTEGER PRIMARY KEY,
    article_id       INTEGER NOT NULL REFERENCES articles(id),
    run_id           TEXT,
    scored_at        TEXT NOT NULL,
    scored_by        TEXT NOT NULL,      -- provider:model
    code_version     TEXT,
    prompt_hash      TEXT,               -- sha256 of the full scoring prompt
    text_label       TEXT,               -- "Article full text" / "Article summary"
    text             TEXT,               -- exactly the text the model saw
    transport_score  INTEGER,
    transport_reason TEXT,
    ai_score         INTEGER,
    ai_reason        TEXT,
    gis_score        INTEGER,
    gis_reason       TEXT,
    total_score      INTEGER,
    error            TEXT,               -- set when the scoring call failed
    market           TEXT,               -- models.Market label (v0.6)
    article_type     TEXT                -- models.ArticleType label (v0.6)
);
CREATE INDEX IF NOT EXISTS scores_article ON scores(article_id);
CREATE INDEX IF NOT EXISTS scores_reuse ON scores(scored_by, prompt_hash);

CREATE TABLE IF NOT EXISTS summaries (
    id             INTEGER PRIMARY KEY,
    article_id     INTEGER NOT NULL REFERENCES articles(id),
    run_id         TEXT,
    summarised_at  TEXT NOT NULL,
    summarised_by  TEXT NOT NULL,      -- provider:model
    code_version   TEXT,
    prompt_hash    TEXT,               -- sha256 of the full digest prompt
    title_en       TEXT,
    summary        TEXT,
    why_it_matters TEXT,
    error          TEXT,               -- set when the digest call failed
    one_liner      TEXT                -- WhatsApp one-line summary (digest_whatsapp.py)
);
CREATE INDEX IF NOT EXISTS summaries_article ON summaries(article_id);

CREATE TABLE IF NOT EXISTS digest_items (
    run_id        TEXT NOT NULL,
    article_id    INTEGER NOT NULL REFERENCES articles(id),
    score_id      INTEGER REFERENCES scores(id),
    summary_id    INTEGER REFERENCES summaries(id),
    digest_status TEXT,                  -- qualified, ai headline, notable, below threshold, scoring failed
    published     INTEGER NOT NULL DEFAULT 0,
    section       TEXT,                  -- "its" or "ai daily brief" when published
    PRIMARY KEY (run_id, article_id)
);

CREATE TABLE IF NOT EXISTS aidb_episodes (
    date   TEXT PRIMARY KEY,             -- YYYY-MM-DD
    url    TEXT,
    title  TEXT,
    lead   TEXT
);

CREATE TABLE IF NOT EXISTS aidb_story_sets (
    id            INTEGER PRIMARY KEY,
    episode_date  TEXT NOT NULL REFERENCES aidb_episodes(date),
    model         TEXT NOT NULL,         -- provider:model that grouped and summarised
    run_id        TEXT,
    saved_at      TEXT,
    code_version  TEXT,
    result        TEXT NOT NULL,         -- JSON: the full build_stories() result
    UNIQUE (episode_date, model)
);
"""


# ------------------------------------------------------------
# Connection
# ------------------------------------------------------------

def connect(path: Path | None = None) -> sqlite3.Connection:
    # DB_PATH is looked up at call time, so tests can point it elsewhere
    path = path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    migrate(conn)
    return conn


# Columns added after a table was first created: (table, column, definition)
ADDED_COLUMNS = [
    ("digest_items", "summary_id", "INTEGER REFERENCES summaries(id)"),   # v0.4
    ("summaries", "one_liner", "TEXT"),                                   # v0.5
    ("scores", "market", "TEXT"),                                         # v0.6
    ("scores", "article_type", "TEXT"),                                   # v0.6
]


def migrate(conn: sqlite3.Connection) -> None:
    # CREATE TABLE IF NOT EXISTS does not add new columns to an existing
    # database, so add any that are missing
    for table, column, definition in ADDED_COLUMNS:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


@contextmanager
def session(path: Path | None = None):
    """Open, commit on success (roll back on error), always close."""
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def code_version() -> str | None:
    # Short git commit, so stored results can be traced to the code (rubric,
    # prompts) that produced them ("+dirty" when there were uncommitted changes)
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        return f"{commit}+dirty" if dirty else commit
    except (OSError, subprocess.CalledProcessError):
        return None


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


# ------------------------------------------------------------
# Runs
# ------------------------------------------------------------

def start_run(conn: sqlite3.Connection, kind: str, run_id: str | None = None) -> str:
    run_id = run_id or llm.RUN_ID
    settings = {
        "provider": llm.get_provider(),
        "models": {task: llm.describe(task) for task in ("scoring", "digest", "transcript")},
        "min_total_score": MIN_TOTAL_SCORE,
        "max_content_words": MAX_CONTENT_WORDS,
        "recent_hours": RECENT_HOURS,
    }
    conn.execute(
        "INSERT OR IGNORE INTO runs (run_id, kind, started_at, code_version, settings) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, kind, now_utc(), code_version(), json.dumps(settings)),
    )
    return run_id


# ------------------------------------------------------------
# Articles, scores, digest items
# ------------------------------------------------------------

def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def upsert_article(conn: sqlite3.Connection, article: Article, run_id: str | None) -> int:
    # Keeps the first published date and the longest full text seen
    now = now_utc()
    row = conn.execute(
        """
        INSERT INTO articles (url, title, source, published_at, summary, content,
                              first_seen_run, first_seen_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title        = excluded.title,
            source       = excluded.source,
            published_at = COALESCE(articles.published_at, excluded.published_at),
            summary      = COALESCE(excluded.summary, articles.summary),
            content      = CASE WHEN length(COALESCE(excluded.content, ''))
                                   > length(COALESCE(articles.content, ''))
                                THEN excluded.content ELSE articles.content END,
            last_seen_at = excluded.last_seen_at
        RETURNING id
        """,
        (article.url, article.title, article.source, iso(article.published_at),
         article.summary, article.content, run_id, now, now),
    ).fetchone()
    return row["id"]


def reuse_scores(conn: sqlite3.Connection, articles: list[Article]) -> list[Article]:
    """Apply stored scores where the current scoring model has already scored
    an identical prompt; return the articles that still need scoring."""
    from .scoring import scoring_prompt

    scored_by = llm.describe("scoring")
    to_score = []
    for article in articles:
        row = conn.execute(
            "SELECT * FROM scores WHERE scored_by = ? AND prompt_hash = ? AND error IS NULL "
            "ORDER BY id DESC LIMIT 1",
            (scored_by, prompt_hash(scoring_prompt(article))),
        ).fetchone()
        if row is None:
            to_score.append(article)
            continue
        article.scored_by = row["scored_by"]
        article.score_id = row["id"]
        for field in ("transport", "ai", "gis"):
            setattr(article, f"{field}_score", row[f"{field}_score"])
            setattr(article, f"{field}_reason", row[f"{field}_reason"])
        article.total_score = row["total_score"]
        article.market = row["market"]
        article.article_type = row["article_type"]
    return to_score


def insert_score(conn: sqlite3.Connection, article_id: int, article: Article, run_id: str | None) -> int:
    from .scoring import scoring_prompt, text_for_scoring

    text_label, text = text_for_scoring(article)
    cur = conn.execute(
        """
        INSERT INTO scores (article_id, run_id, scored_at, scored_by, code_version, prompt_hash,
                            text_label, text, transport_score, transport_reason, ai_score,
                            ai_reason, gis_score, gis_reason, total_score, error,
                            market, article_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (article_id, run_id, now_utc(), article.scored_by, code_version(),
         prompt_hash(scoring_prompt(article)), text_label, text,
         article.transport_score, article.transport_reason, article.ai_score,
         article.ai_reason, article.gis_score, article.gis_reason,
         article.total_score, article.scoring_error,
         article.market, article.article_type),
    )
    return cur.lastrowid


def insert_summary(conn: sqlite3.Connection, article_id: int, article: Article, run_id: str | None) -> int:
    from .digest import digest_prompt

    cur = conn.execute(
        """
        INSERT INTO summaries (article_id, run_id, summarised_at, summarised_by, code_version,
                               prompt_hash, title_en, summary, why_it_matters, error, one_liner)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (article_id, run_id, now_utc(), article.summarised_by, code_version(),
         prompt_hash(digest_prompt(article)), article.title_en, article.digest_summary,
         article.why_it_matters, article.summary_error, article.one_liner),
    )
    return cur.lastrowid


def published_urls(conn: sqlite3.Connection) -> set[str]:
    """URLs of articles published in any earlier pipeline run (including
    runs imported from v0.3). Backfill runs never publish."""
    return {
        row["url"] for row in conn.execute(
            "SELECT DISTINCT a.url FROM digest_items d "
            "JOIN articles a ON a.id = d.article_id "
            "JOIN runs r ON r.run_id = d.run_id "
            "WHERE d.published = 1 AND r.kind LIKE 'pipeline%'"
        )
    }


# Disabled: only same-day re-runs would benefit. To enable, uncomment this,
# its call in main.py and the skip in digest.summarise_articles().
#
# def reuse_summaries(conn: sqlite3.Connection, articles: list[Article]) -> None:
#     """Fill the summary fields of articles whose identical digest prompt the
#     current digest model has already summarised."""
#     from .digest import digest_prompt
#
#     summarised_by = llm.describe("digest")
#     for article in articles:
#         row = conn.execute(
#             "SELECT * FROM summaries WHERE summarised_by = ? AND prompt_hash = ? "
#             "AND error IS NULL ORDER BY id DESC LIMIT 1",
#             (summarised_by, prompt_hash(digest_prompt(article))),
#         ).fetchone()
#         if row is None:
#             continue
#         article.summarised_by = row["summarised_by"]
#         article.summary_id = row["id"]
#         article.title_en = row["title_en"]
#         article.digest_summary = row["summary"]
#         article.why_it_matters = row["why_it_matters"]


def save_articles(conn: sqlite3.Connection, run_id: str, articles: list[Article]) -> None:
    """Upsert each article, store its score if it is new (not reused) and its
    digest summary if it has one, and record its digest status for this run."""
    for article in articles:
        article_id = upsert_article(conn, article, run_id)
        if article.score_id is None and article.scored_by:
            article.score_id = insert_score(conn, article_id, article, run_id)
        if article.summary_id is None and article.summarised_by:
            article.summary_id = insert_summary(conn, article_id, article, run_id)
        section = None
        if article.published:
            section = SECTION_AIDB if article.digest_status == AI_HEADLINE else SECTION_ITS
        conn.execute(
            "INSERT OR REPLACE INTO digest_items "
            "(run_id, article_id, score_id, summary_id, digest_status, published, section) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, article_id, article.score_id, article.summary_id,
             article.digest_status, int(article.published), section),
        )


# ------------------------------------------------------------
# AI Daily Brief story sets
# ------------------------------------------------------------

def load_story_set(conn: sqlite3.Connection, date: str, model: str) -> dict | None:
    row = conn.execute(
        "SELECT result FROM aidb_story_sets WHERE episode_date = ? AND model = ?",
        (date, model),
    ).fetchone()
    return json.loads(row["result"]) if row else None


def save_story_set(conn: sqlite3.Connection, result: dict) -> None:
    conn.execute(
        "INSERT INTO aidb_episodes (date, url, title, lead) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(date) DO UPDATE SET url = excluded.url, title = excluded.title, "
        "lead = excluded.lead",
        (result["date"], result.get("url"), result.get("episode_title"), result.get("episode_lead")),
    )
    conn.execute(
        "INSERT OR REPLACE INTO aidb_story_sets "
        "(episode_date, model, run_id, saved_at, code_version, result) VALUES (?, ?, ?, ?, ?, ?)",
        (result["date"], result["model"], result.get("run_id"), result.get("saved_at"),
         result.get("code_version"), json.dumps(result, ensure_ascii=False)),
    )


# ------------------------------------------------------------
# One-off import of the v0.3 files
# ------------------------------------------------------------

def import_legacy(conn: sqlite3.Connection) -> None:
    """Import output/scored-articles.jsonl (the v0.3 candidate pool) and
    output/aidailybrief/<date>/stories__*.json. Safe to run twice: pool runs
    already in the database and story sets already stored are skipped."""
    # Story sets
    added = 0
    for path in sorted((PROJECT_ROOT / AIDB_DIR).glob("*/stories__*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        if load_story_set(conn, result["date"], result["model"]) is None:
            save_story_set(conn, result)
            added += 1
    print(f"Story sets imported: {added}")

    # Candidate pool
    pool = PROJECT_ROOT / "output" / "scored-articles.jsonl"
    if not pool.exists():
        print("No scored-articles.jsonl to import")
        return
    rows = [json.loads(line) for line in pool.read_text(encoding="utf-8").splitlines() if line.strip()]
    known_runs = {r["run_id"] for r in conn.execute("SELECT run_id FROM runs")}
    imported = 0
    for r in rows:
        if r["run_id"] in known_runs:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO runs (run_id, kind, started_at, code_version, settings) "
            "VALUES (?, 'pipeline (imported)', ?, ?, ?)",
            (r["run_id"], r["saved_at"], r.get("code_version"),
             json.dumps({"min_total_score": r.get("min_total_score"),
                         "max_content_words": r.get("max_content_words")})),
        )
        full = r["text_label"] == "Article full text"
        article = Article(
            title=r["title"], url=r["url"], source=r["source"],
            published_at=datetime.fromisoformat(r["published_at"]) if r["published_at"] else None,
            summary=None if full else r["text"],
            content=r["text"] if full else None,
        )
        article_id = upsert_article(conn, article, r["run_id"])
        cur = conn.execute(
            """
            INSERT INTO scores (article_id, run_id, scored_at, scored_by, code_version, prompt_hash,
                                text_label, text, transport_score, transport_reason, ai_score,
                                ai_reason, gis_score, gis_reason, total_score, error)
            VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (article_id, r["run_id"], r["saved_at"], r["scored_by"], r.get("code_version"),
             r["text_label"], r["text"], r["transport_score"], r["transport_reason"],
             r["ai_score"], r["ai_reason"], r["gis_score"], r["gis_reason"],
             r["total_score"], r["scoring_error"]),
        )
        published = bool(r["published"])
        section = (SECTION_AIDB if r["digest_status"] == AI_HEADLINE else SECTION_ITS) if published else None
        conn.execute(
            "INSERT OR REPLACE INTO digest_items "
            "(run_id, article_id, score_id, digest_status, published, section) VALUES (?, ?, ?, ?, ?, ?)",
            (r["run_id"], article_id, cur.lastrowid, r["digest_status"], int(published), section),
        )
        imported += 1
    print(f"Pool rows imported: {imported} of {len(rows)}")


# ------------------------------------------------------------
# Command line
# ------------------------------------------------------------

def print_stats(conn: sqlite3.Connection) -> None:
    print(f"Database: {DB_PATH}")
    for table in ("runs", "articles", "scores", "summaries", "digest_items", "aidb_episodes", "aidb_story_sets"):
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<16} {n:>6}")
    print("\nArticles by source:")
    for row in conn.execute(
        "SELECT source, COUNT(*) AS n FROM articles GROUP BY source ORDER BY n DESC"
    ):
        print(f"  {row['n']:>5}  {row['source']}")
    print("\nScores by model:")
    for row in conn.execute(
        "SELECT scored_by, COUNT(*) AS n, SUM(error IS NOT NULL) AS errors "
        "FROM scores GROUP BY scored_by ORDER BY n DESC"
    ):
        print(f"  {row['n']:>5}  {row['scored_by']}  ({row['errors']} failed)")


def main() -> None:
    parser = argparse.ArgumentParser(description="News repository (SQLite)")
    parser.add_argument("--import-legacy", action="store_true",
                        help="import output/scored-articles.jsonl and the AI Daily Brief story JSON files")
    parser.add_argument("--stats", action="store_true", help="print table counts")
    args = parser.parse_args()

    with session() as conn:
        if args.import_legacy:
            start_run(conn, "import")
            import_legacy(conn)
        if args.stats or not args.import_legacy:
            print_stats(conn)


if __name__ == "__main__":
    main()

"""Tests for the shared read-only queries (web/queries.py).

Each test gets an empty temporary database from the autouse `temp_db`
fixture in conftest.py (a Path; the real news.db is never opened). The
`its_db` fixture below fills it with a few runs and articles.
"""

import sqlite3

import pytest

from aimobility_news import db
from aimobility_news.web import queries


# ------------------------------------------------------------
# Helpers to insert rows (plain SQL, only the columns the queries need)
# ------------------------------------------------------------

def add_run(conn, run_id, kind="pipeline"):
    conn.execute(
        "INSERT INTO runs (run_id, kind, started_at) VALUES (?, ?, ?)",
        (run_id, kind, f"{run_id[:10]}T12:00:00+00:00"),
    )


def add_article(conn, url, title, source="Test Source", published_at=None) -> int:
    cursor = conn.execute(
        """INSERT INTO articles (url, title, source, published_at, first_seen_at, last_seen_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (url, title, source, published_at, "2026-11-01T00:00:00+00:00", "2026-11-01T00:00:00+00:00"),
    )
    return cursor.lastrowid          # the new row's id (INTEGER PRIMARY KEY)


def add_item(conn, run_id, article_id, status, published):
    conn.execute(
        """INSERT INTO digest_items (run_id, article_id, digest_status, published)
           VALUES (?, ?, ?, ?)""",
        (run_id, article_id, status, int(published)),
    )


# ------------------------------------------------------------
# Fixture
# ------------------------------------------------------------
RUN1 = "2026-11-03 20:00:00"
RUN2 = "2026-11-04 20:00:00"
RUN3 = "2026-11-05 20:00:00"

@pytest.fixture
def its_db(temp_db):
    """A database with:
    - two pipeline runs, "2026-11-03 20:00:00" and a later "2026-11-04 20:00:00";
    - article A in both runs: "notable", not published in the first,
      "qualified" and published in the second;
    - article B in the second run only: "below threshold", not published;
    - an AI Daily Brief article (source queries.AIDB_SOURCE), "ai headline",
      published in the second run.
    Returns the database path.
    """
    # db.session() creates the schema and commits when the block ends, so the
    # data is on disk before a test opens the file read-only.
    with db.session(temp_db) as conn:
        add_run(conn, RUN1)
        add_run(conn, RUN2)

        id1 = add_article(conn, "https://example.test/a","Article A" )
        id2 = add_article(conn, "https://example.test/b","Article B" )
        id3= add_article(conn, "https://example.test/aidb",title =  "Article AIDB", source=queries.AIDB_SOURCE )

        add_item(conn, RUN1, id1,status="notable", published=0)
        add_item(conn, RUN2, id1, status = "qualified", published=1)
        add_item(conn, RUN2, id2, status = "below threshold", published=0)
        add_item(conn, RUN2, id3, status= "ai headline", published=1)
    
    return temp_db

# ------------------------------------------------------------
# load_its_rows()
# ------------------------------------------------------------

def test_latest_run_wins(its_db):
    """Article A appears once, from its latest run (RUN2). include_all=True
    keeps A's unpublished RUN1 row in the query, so the test can catch an
    older run winning."""
    conn = queries.connect_read_only(its_db)
    rows = queries.load_its_rows(conn, include_all=True)
    conn.close()

    a_rows = [row for row in rows if row["url"] == "https://example.test/a"]
    assert len(a_rows) == 1
    assert a_rows[0]["run_id"] == RUN2
    assert a_rows[0]["digest_status"] == "qualified"   


def test_published_only_by_default(its_db):
    """Without include_all only published ITS articles come back. The exact
    set comparison also fails on an empty result."""
    conn = queries.connect_read_only(its_db)
    rows = queries.load_its_rows(conn, include_all=False)
    conn.close()

    urls = {row["url"] for row in rows}
    assert urls == {"https://example.test/a"}


def test_ai_daily_brief_articles_are_excluded(its_db):
    """The AI Daily Brief article is published, yet never returned, with or
    without include_all."""
    conn = queries.connect_read_only(its_db)
    rows1 = queries.load_its_rows(conn, include_all=True)
    rows2 = queries.load_its_rows(conn, include_all=False)
    conn.close()

    a1_rows = [row for row in rows1 if row["url"] == "https://example.test/aidb"]
    assert len(a1_rows) == 0

    a2_rows = [row for row in rows2 if row["url"] == "https://example.test/aidb"]
    assert len(a2_rows) == 0

  
# ------------------------------------------------------------
# Connection and dates
# ------------------------------------------------------------

def test_connection_is_read_only(its_db):
    """Writing through connect_read_only() fails (RUN3 is a new run_id, so the
    only reason the INSERT can fail is the read-only mode)."""
    conn = queries.connect_read_only(its_db)
    with pytest.raises(sqlite3.OperationalError):
        add_run(conn, RUN3)
    conn.close()
  

def test_local_day_handles_missing_and_naive_dates():
    """Missing dates give None; a naive date-time keeps its day. Only naive
    strings are tested: an aware one is converted to this machine's local
    time, so its expected day would depend on where the test runs."""
    assert queries.local_day(None) is None
    assert queries.local_day("") is None
    assert queries.local_day("2026-11-03T23:30:00") == "2026-11-03"

"""Tests for the SQLite repository (db.py) and the code that writes to it:
score reuse, summaries, migration, legacy import, AI Daily Brief story sets
and the resumable backfill."""

import json
import sqlite3
import sys

import pytest

from aimobility_news import aidailybrief_transcript, backfill_aidb, db, digest, llm
from aimobility_news.ranking import QUALIFIED, NOTABLE, BELOW_THRESHOLD
from aimobility_news.scoring import score_articles

from conftest import make_article


def count(conn, table, where="1=1", params=()):
    return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()[0]


def scored(article, fake_llm):
    score_articles([article])
    return article


# ------------------------------------------------------------
# Schema and migration
# ------------------------------------------------------------

def test_connect_creates_all_tables(temp_db):
    with db.session() as conn:
        tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert temp_db.exists()
    assert tables >= {"runs", "articles", "scores", "summaries", "digest_items",
                      "aidb_episodes", "aidb_story_sets"}


def test_migrate_adds_summary_id_to_an_older_database(temp_db):
    # digest_items as created before summaries existed, with one row
    temp_db.parent.mkdir(parents=True)
    old = sqlite3.connect(temp_db)
    old.executescript("""
        CREATE TABLE digest_items (
            run_id TEXT NOT NULL, article_id INTEGER NOT NULL, score_id INTEGER,
            digest_status TEXT, published INTEGER NOT NULL DEFAULT 0, section TEXT,
            PRIMARY KEY (run_id, article_id));
        INSERT INTO digest_items VALUES ('r1', 1, NULL, 'qualified', 1, 'its');
    """)
    old.commit()
    old.close()

    with db.session() as conn:
        columns = [r["name"] for r in conn.execute("PRAGMA table_info(digest_items)")]
        row = conn.execute("SELECT * FROM digest_items").fetchone()
    assert "summary_id" in columns
    assert (row["run_id"], row["digest_status"], row["summary_id"]) == ("r1", "qualified", None)

    # A second connect does not try to add the column again
    with db.session():
        pass


def test_migrate_adds_one_liner_to_a_v04_summaries_table(temp_db):
    temp_db.parent.mkdir(parents=True)
    old = sqlite3.connect(temp_db)
    old.executescript("""
        CREATE TABLE summaries (
            id INTEGER PRIMARY KEY, article_id INTEGER NOT NULL, run_id TEXT,
            summarised_at TEXT NOT NULL, summarised_by TEXT NOT NULL, code_version TEXT,
            prompt_hash TEXT, title_en TEXT, summary TEXT, why_it_matters TEXT, error TEXT);
        INSERT INTO summaries (article_id, summarised_at, summarised_by, summary)
        VALUES (1, 'now', 'openai:m', 'Old summary.');
    """)
    old.commit()
    old.close()

    with db.session() as conn:
        columns = [r["name"] for r in conn.execute("PRAGMA table_info(summaries)")]
        row = conn.execute("SELECT summary, one_liner FROM summaries").fetchone()
    assert "one_liner" in columns
    assert (row["summary"], row["one_liner"]) == ("Old summary.", None)


# ------------------------------------------------------------
# Articles
# ------------------------------------------------------------

def test_upsert_keeps_one_row_per_url_with_longest_text_and_first_date():
    first = make_article("Story", content="short text")
    later = make_article("Story", content="a much longer full text of the story")
    later.published_at = None
    again = make_article("Story", content="short again")

    with db.session() as conn:
        ids = {db.upsert_article(conn, a, "r1") for a in (first, later, again)}
        row = conn.execute("SELECT * FROM articles").fetchone()
        assert count(conn, "articles") == 1
    assert len(ids) == 1
    assert row["content"] == "a much longer full text of the story"
    assert row["published_at"] == "2026-11-03T01:00:00+00:00"
    assert row["first_seen_run"] == "r1"


# ------------------------------------------------------------
# Scores
# ------------------------------------------------------------

def test_stored_score_is_reused_for_an_identical_prompt(fake_llm):
    article = scored(make_article("Bus AI", content="Full text about AI buses."), fake_llm)
    with db.session() as conn:
        db.start_run(conn, "pipeline")
        db.save_articles(conn, llm.RUN_ID, [article])

    same = make_article("Bus AI", content="Full text about AI buses.")
    with db.session() as conn:
        to_score = db.reuse_scores(conn, [same])

    assert to_score == []
    assert same.score_id == article.score_id
    assert (same.transport_score, same.ai_score, same.gis_score, same.total_score) == (3, 4, 1, 23)
    assert same.ai_reason == "a"
    assert fake_llm.count("scoring") == 1


def test_changed_text_or_model_means_a_fresh_score(fake_llm):
    article = scored(make_article("Bus AI", content="Original text."), fake_llm)
    with db.session() as conn:
        db.save_articles(conn, "r1", [article])

    changed = make_article("Bus AI", content="Updated text.")
    with db.session() as conn:
        assert db.reuse_scores(conn, [changed]) == [changed]

    llm.set_provider("ollama")
    same_text = make_article("Bus AI", content="Original text.")
    with db.session() as conn:
        assert db.reuse_scores(conn, [same_text]) == [same_text]


def test_failed_score_is_stored_but_not_reused(fake_llm):
    fake_llm.fail["Broken"] = TimeoutError("no answer")
    ok = make_article("Fine")
    broken = make_article("Broken")
    score_articles([ok, broken])
    with db.session() as conn:
        db.save_articles(conn, "r1", [ok, broken])
        error = conn.execute("SELECT error FROM scores WHERE article_id = "
                             "(SELECT id FROM articles WHERE title = 'Broken')").fetchone()[0]
        assert count(conn, "scores") == 2
        assert db.reuse_scores(conn, [make_article("Broken")])  # still needs scoring
    assert error == "TimeoutError: no answer"


def test_reused_score_is_not_stored_twice(fake_llm):
    article = scored(make_article("Rail"), fake_llm)
    with db.session() as conn:
        db.save_articles(conn, "r1", [article])

    rerun = make_article("Rail")
    with db.session() as conn:
        db.reuse_scores(conn, [rerun])
        db.save_articles(conn, "r2", [rerun])
        assert count(conn, "scores") == 1
        assert count(conn, "digest_items") == 2
        assert {r["score_id"] for r in conn.execute("SELECT score_id FROM digest_items")} == {article.score_id}


# ------------------------------------------------------------
# Summaries and digest items
# ------------------------------------------------------------

def test_summaries_are_stored_and_linked_to_the_run(fake_llm):
    fake_llm.fail["Failed"] = TimeoutError("slow")
    good = make_article("Good", digest_status=QUALIFIED, published=True)
    failed = make_article("Failed", digest_status=NOTABLE, published=True)
    unpublished = make_article("Unpublished", digest_status=BELOW_THRESHOLD)
    articles = [good, failed, unpublished]
    score_articles(articles)

    markdown = digest.generate_digest(articles)

    with db.session() as conn:
        db.start_run(conn, "pipeline")
        db.save_articles(conn, llm.RUN_ID, articles)
        rows = {r["title"]: r for r in conn.execute(
            "SELECT a.title, d.published, d.section, d.summary_id, m.summary, m.why_it_matters, "
            "m.summarised_by, m.prompt_hash, m.error "
            "FROM digest_items d JOIN articles a ON a.id = d.article_id "
            "LEFT JOIN summaries m ON m.id = d.summary_id")}
        assert count(conn, "summaries") == 2

    assert fake_llm.count("digest") == 2          # published articles only
    assert rows["Good"]["summary"] == "Summary of Good. Second sentence."
    assert rows["Good"]["why_it_matters"] == "Why Good"
    assert rows["Good"]["summarised_by"] == llm.describe("digest")
    assert rows["Good"]["prompt_hash"] == db.prompt_hash(digest.digest_prompt(good))
    assert rows["Good"]["section"] == db.SECTION_ITS
    assert rows["Failed"]["summary"] is None and rows["Failed"]["error"] == "TimeoutError: slow"
    assert rows["Unpublished"]["summary_id"] is None and rows["Unpublished"]["published"] == 0
    assert "Summary of Good" in markdown
    assert "Summary unavailable" in markdown


def test_published_urls_are_from_published_pipeline_items_only(fake_llm):
    published = make_article("Published", digest_status=QUALIFIED, published=True)
    unpublished = make_article("Unpublished", digest_status=BELOW_THRESHOLD)
    backfilled = make_article("Backfilled", digest_status=QUALIFIED)
    with db.session() as conn:
        db.start_run(conn, "pipeline", run_id="p1")
        db.save_articles(conn, "p1", [published, unpublished])
        db.start_run(conn, "backfill aidb", run_id="b1")
        db.save_articles(conn, "b1", [backfilled])
        assert db.published_urls(conn) == {published.url}


# ------------------------------------------------------------
# AI Daily Brief story sets
# ------------------------------------------------------------

def story_set(date, model, n_stories=2):
    return {
        "run_id": "r1", "saved_at": "2026-11-03T00:00:00+00:00", "code_version": "test",
        "model": model, "date": date, "url": f"https://aidailybrief.ai/e/{date}",
        "episode_title": f"Episode {date}", "episode_lead": "Lead.",
        "headings": [], "groupings": [],
        "stories": [
            {"id": f"main-episode-{n}", "section": "main episode", "title": f"Story {n}",
             "url": f"https://aidailybrief.ai/e/{date}#story-{n}",
             "window": {"start": "00:00:00", "end": "00:05:00"},
             "excerpt": "excerpt", "summary_error": None,
             "summary": {"headline": f"{date} story {n}", "summary": f"Summary {n}.",
                         "key_points": ["point"]}}
            for n in range(1, n_stories + 1)
        ],
    }


def test_story_set_round_trip_one_per_episode_and_model():
    with db.session() as conn:
        db.save_story_set(conn, story_set("2026-10-29", "openai:m"))
        db.save_story_set(conn, story_set("2026-10-29", "ollama:m", n_stories=3))
        db.save_story_set(conn, story_set("2026-10-29", "openai:m"))   # replaces, not adds
        assert count(conn, "aidb_episodes") == 1
        assert count(conn, "aidb_story_sets") == 2
        loaded = db.load_story_set(conn, "2026-10-29", "ollama:m")
        assert db.load_story_set(conn, "2026-10-30", "openai:m") is None
    assert len(loaded["stories"]) == 3


def test_build_stories_reuses_a_stored_story_set(monkeypatch):
    model = llm.describe("transcript")
    with db.session() as conn:
        db.save_story_set(conn, story_set("2026-10-29", model))

    def no_fetch(date):
        raise AssertionError("fetched the episode although its stories are stored")
    monkeypatch.setattr(aidailybrief_transcript, "fetch_episode", no_fetch)

    result = aidailybrief_transcript.build_stories("2026-10-29")
    assert [s["title"] for s in result["stories"]] == ["Story 1", "Story 2"]


# ------------------------------------------------------------
# Legacy import
# ------------------------------------------------------------

def test_legacy_import_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "PROJECT_ROOT", tmp_path)
    episode_dir = tmp_path / db.AIDB_DIR / "2026-10-29"
    episode_dir.mkdir(parents=True)
    (episode_dir / "stories__openai_m.json").write_text(
        json.dumps(story_set("2026-10-29", "openai:m")), encoding="utf-8")

    def pool_row(run_id, title, published):
        return {
            "run_id": run_id, "saved_at": "2026-11-03T02:00:00+00:00", "code_version": "abc",
            "min_total_score": 11, "max_content_words": 1500,
            "title": title, "url": f"https://example.test/{title}", "source": "Test Source",
            "published_at": "2026-11-03T01:00:00+00:00",
            "text_label": "Article full text", "text": "Full text.",
            "scored_by": "openai:m", "transport_score": 3, "transport_reason": "t",
            "ai_score": 4, "ai_reason": "a", "gis_score": 1, "gis_reason": "g",
            "total_score": 23, "scoring_error": None,
            "digest_status": QUALIFIED if published else BELOW_THRESHOLD, "published": published,
        }
    rows = [pool_row("2026-11-03 10:00:00", "one", True),
            pool_row("2026-11-03 10:00:00", "two", False),
            pool_row("2026-11-03 11:00:00", "one", True)]
    (tmp_path / "output").mkdir(exist_ok=True)
    (tmp_path / "output" / "scored-articles.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    def snapshot():
        with db.session() as conn:
            return {t: count(conn, t) for t in
                    ("runs", "articles", "scores", "digest_items", "aidb_story_sets")}

    with db.session() as conn:
        db.import_legacy(conn)
    first = snapshot()
    with db.session() as conn:
        db.import_legacy(conn)

    assert first == {"runs": 2, "articles": 2, "scores": 3, "digest_items": 3, "aidb_story_sets": 1}
    assert snapshot() == first


# ------------------------------------------------------------
# Backfill
# ------------------------------------------------------------

def test_backfill_resumes_after_a_crash_without_repeating_llm_calls(monkeypatch, fake_llm):
    # Two episodes; the split is faked (counted in `splits`) but goes through
    # the real story-set cache in the database, and scoring is real with a
    # fake LLM. The first run "crashes" (KeyboardInterrupt, not caught by the
    # backfill) while scoring episode 2, after its stories were saved.
    from aimobility_news.aidailybrief import fetch_aidailybrief_articles  # noqa: F401 (patched below)

    dates = ["2026-10-28", "2026-10-29"]
    editions = [make_article(f"Episode {d}", url=f"https://aidailybrief.ai/e/{d}") for d in dates]
    monkeypatch.setattr(backfill_aidb, "fetch_aidailybrief_articles", lambda: editions)

    splits = []

    def fake_build_stories(date, refresh=False):
        model = llm.describe("transcript")
        with db.session() as conn:
            saved = db.load_story_set(conn, date, model)
        if saved:
            return saved
        splits.append(date)
        result = story_set(date, model)
        with db.session() as conn:
            db.save_story_set(conn, result)
        return result
    monkeypatch.setattr(backfill_aidb, "build_stories", fake_build_stories)

    def run_backfill(run_id):
        monkeypatch.setattr(llm, "RUN_ID", run_id)
        monkeypatch.setattr(sys, "argv", ["backfill_aidb", "--since", dates[0], "--until", dates[-1]])
        backfill_aidb.main()

    fake_llm.fail["2026-10-29 story 1"] = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        run_backfill("2026-11-03 20:00:00")

    with db.session() as conn:
        assert count(conn, "aidb_story_sets") == 2          # both splits saved
        assert count(conn, "scores") == 2                   # episode 1 only
    assert splits == dates
    assert fake_llm.count("scoring") == 3                   # 2 + the crashed call

    fake_llm.fail.clear()
    fake_llm.calls.clear()
    run_backfill("2026-11-03 21:00:00")

    assert splits == dates                                  # no new splits
    assert fake_llm.count("scoring") == 2                   # episode 2's stories only
    with db.session() as conn:
        assert count(conn, "scores") == 4
        assert count(conn, "articles") == 4
        assert count(conn, "digest_items", "run_id = ?", ("2026-11-03 21:00:00",)) == 4
        assert count(conn, "digest_items", "published = 1") == 0

    # A third run makes no LLM calls at all
    fake_llm.calls.clear()
    run_backfill("2026-11-03 22:00:00")
    assert fake_llm.calls == []
    assert splits == dates

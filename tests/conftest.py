"""Shared fixtures. Every test gets its own temporary database, and no test
makes a real LLM call or touches output/db/news.db."""

from datetime import datetime, timezone

import pytest

from aimobility_news import db, llm
from aimobility_news.digest import DigestEntry
from aimobility_news.digest_whatsapp import OneLiner, OneLiners
from aimobility_news.models import Article
from aimobility_news.scoring import ArticleScore


REAL_DB = db.DB_PATH


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "db" / "news.db"
    monkeypatch.setattr(db, "DB_PATH", path)
    monkeypatch.setattr(db, "code_version", lambda: "test")
    monkeypatch.setattr(llm, "RUN_ID", "2026-11-03 20:00:00")
    llm.set_provider("openai")
    yield path
    llm.set_provider("openai")
    assert db.DB_PATH != REAL_DB


class FakeLLM:
    """Stands in for llm.parse(): records each call by task and label and
    returns a fixed answer. Labels in `fail` raise the given exception."""

    def __init__(self):
        self.calls = []
        self.fail = {}

    def __call__(self, prompt, schema, task, provider=None, label=""):
        self.calls.append((task, label))
        if label in self.fail:
            raise self.fail[label]
        if schema is ArticleScore:
            return ArticleScore(transport_reason="t", transport_score=3,
                                ai_reason="a", ai_score=4, gis_reason="g", gis_score=1,
                                market="Singapore", article_type="news")
        if schema is DigestEntry:
            return DigestEntry(title_en="", summary=f"Summary of {label}. Second sentence.",
                               why_it_matters=f"Why {label}")
        if schema is OneLiners:
            n_items = prompt.count("\nSummary: ")
            return OneLiners(lines=[OneLiner(number=n, line=f"One-liner {n}")
                                    for n in range(1, n_items + 1)])
        raise AssertionError(f"unexpected schema {schema}")

    def count(self, task):
        return sum(1 for t, _ in self.calls if t == task)


@pytest.fixture
def fake_llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(llm, "parse", fake)
    return fake


def make_article(title="Article", url=None, content=None, summary="A short summary.", **kwargs):
    return Article(
        title=title,
        url=url or f"https://example.test/{title.replace(' ', '-').lower()}",
        source="Test Source",
        published_at=datetime(2026, 11, 3, 1, 0, tzinfo=timezone.utc),
        summary=summary,
        content=content,
        **kwargs,
    )

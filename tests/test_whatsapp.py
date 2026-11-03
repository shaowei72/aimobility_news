"""Tests for the WhatsApp-ready digest (digest_whatsapp.py)."""

import subprocess
from datetime import datetime

from aimobility_news import db, digest_whatsapp as wa, llm
from aimobility_news.ranking import AI_HEADLINE, BELOW_THRESHOLD, NOTABLE, QUALIFIED

from conftest import make_article


def its(title, status=QUALIFIED, published=True, summary=None, **kwargs):
    article = make_article(title, digest_status=status, published=published, **kwargs)
    article.digest_summary = summary if summary is not None else f"{title} happened. More detail."
    article.why_it_matters = "It matters."
    return article


def headline(title):
    return make_article(title, url=f"https://aidailybrief.ai/e/2026-11-03#{title}",
                        digest_status=AI_HEADLINE, published=True)


def test_selection_qualified_then_notable_capped(monkeypatch):
    monkeypatch.setattr(wa, "WHATSAPP_MAX_ITS", 3)
    ranked = [its("N1", NOTABLE), its("Q1"), its("Below", BELOW_THRESHOLD, published=False),
              its("Q2"), its("N2", NOTABLE), its("Unpublished Q", published=False)]
    assert [a.title for a in wa.select_its_items(ranked)] == ["Q1", "Q2", "N1"]

    monkeypatch.setattr(wa, "WHATSAPP_INCLUDE_NOTABLE", False)
    assert [a.title for a in wa.select_its_items(ranked)] == ["Q1", "Q2"]


def test_one_liners_use_a_single_llm_call(fake_llm):
    articles = [its("A"), its("B"), its("C")]
    wa.add_one_liners(articles)
    assert fake_llm.calls == [("digest", "WhatsApp one-liners")]
    assert [a.one_liner for a in articles] == ["One-liner 1", "One-liner 2", "One-liner 3"]


def test_one_liners_fall_back_to_the_first_sentence(fake_llm):
    fake_llm.fail["WhatsApp one-liners"] = TimeoutError("slow")
    articles = [its("A", summary="Buses got smarter. Then more happened."), its("B")]
    wa.add_one_liners(articles)
    assert [a.one_liner for a in articles] == ["Buses got smarter.", "B happened."]


def test_article_without_a_summary_gets_no_one_liner_and_no_call(fake_llm):
    failed = its("Failed", summary="")
    failed.digest_summary = None
    wa.add_one_liners([failed])
    assert fake_llm.calls == []
    assert failed.one_liner is None


def test_first_sentence_is_capped():
    long = "word " * 100
    assert wa.first_sentence(long).endswith("…")
    assert len(wa.first_sentence(long)) <= 221
    assert wa.first_sentence(None) is None


def test_text_format():
    a = its("Rail *AI* plan")
    a.one_liner = "Operator deploys _vision_ AI on 40 trains."
    b = its("中文标题", title_en="Chinese title")
    text = wa.generate_whatsapp([a, b], [headline("Gemini tops rankings")],
                                day=datetime(2026, 11, 3))
    assert text.splitlines() == [
        "*Daily Briefing — 3 Nov 2026*",
        "",
        "*🚦 Intelligent Transport (ITS)*",
        "",
        "1. *Rail AI plan*",
        "Operator deploys vision AI on 40 trains.",
        a.url,
        "",
        "2. *Chinese title*",
        b.url,
        "",
        "*🤖 AI Daily Brief*",
        "",
        "1. *Gemini tops rankings*",
        "https://aidailybrief.ai/e/2026-11-03#Gemini tops rankings",
    ]


def test_empty_sections_say_so():
    text = wa.generate_whatsapp([], [], day=datetime(2026, 11, 3))
    assert "_No ITS articles today._" in text
    assert "_No AI Daily Brief stories today._" in text


def test_build_respects_limits_and_switches(monkeypatch, fake_llm):
    monkeypatch.setattr(wa, "WHATSAPP_MAX_AIDB", 1)
    ranked = [its("Q1"), its("Q2")]
    text = wa.build_whatsapp(ranked, [headline("H1"), headline("H2")])
    assert "One-liner 1" in text and "H1" in text and "H2" not in text

    fake_llm.calls.clear()
    monkeypatch.setattr(wa, "WHATSAPP_ONE_LINERS", False)
    fresh = [its("Q1"), its("Q2")]
    text = wa.build_whatsapp(fresh, [])
    assert fake_llm.calls == []
    assert "One-liner" not in text and "*Q1*" in text


def test_one_liner_is_stored_with_the_summary(fake_llm):
    article = its("Stored")
    article.summarised_by = llm.describe("digest")
    wa.add_one_liners([article])
    with db.session() as conn:
        db.save_articles(conn, "r1", [article])
        row = conn.execute("SELECT one_liner FROM summaries").fetchone()
    assert row["one_liner"] == "One-liner 1"


def test_clipboard_gets_utf16_with_windows_line_endings(monkeypatch):
    sent = {}

    def fake_run(cmd, input, check, timeout):
        sent["cmd"], sent["input"] = cmd, input
    monkeypatch.setattr(wa.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "run", fake_run)

    assert wa.copy_to_clipboard("*Hi* 🚦\nWrocław") is True
    assert sent["cmd"] == ["clip"]
    assert sent["input"].decode("utf-16-le") == "*Hi* 🚦\r\nWrocław"


def test_clipboard_failure_only_warns(monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("no clip")
    monkeypatch.setattr(wa.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "run", broken)
    assert wa.copy_to_clipboard("text") is False

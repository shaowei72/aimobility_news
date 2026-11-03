"""Tests for feed parsing details in feeds.py: dates without a timezone,
page decoding, and deduplication by canonical URL and title. No network."""

from datetime import datetime, timedelta, timezone

import feedparser
import pytest

from aimobility_news import feeds
from aimobility_news.feeds import canonical_url, deduplicate_articles, entry_published_at, title_key

from conftest import make_article


GASGOO = "Gasgoo Intelligent Connected Vehicles"


def entry_with_date(date_text):
    rss = f"""<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0"><channel><title>t</title>
      <item><title>Item</title><link>https://example.test/a</link>
            <pubDate>{date_text}</pubDate></item>
    </channel></rss>"""
    return feedparser.parse(rss).entries[0]


# ------------------------------------------------------------
# Dates
# ------------------------------------------------------------

def test_gasgoo_date_without_timezone_is_beijing_time():
    published = entry_published_at(entry_with_date("2026-11-02 17:28:04"), GASGOO)
    assert published == datetime(2026, 11, 2, 9, 28, 4, tzinfo=timezone.utc)


@pytest.mark.parametrize("date_text", [
    "Mon, 02 Nov 2026 17:28:04 GMT",
    "Mon, 02 Nov 2026 17:28:04 +0000",
    "2026-11-02T17:28:04Z",
])
def test_a_stated_timezone_is_used_as_given(date_text):
    published = entry_published_at(entry_with_date(date_text), GASGOO)
    assert published == datetime(2026, 11, 2, 17, 28, 4, tzinfo=timezone.utc)


def test_a_stated_offset_is_converted_to_utc():
    published = entry_published_at(entry_with_date("Mon, 02 Nov 2026 17:28:04 +0800"), GASGOO)
    assert published == datetime(2026, 11, 2, 9, 28, 4, tzinfo=timezone.utc)


def test_other_sources_keep_utc_for_dates_without_timezone():
    published = entry_published_at(entry_with_date("2026-11-02 17:28:04"), "Electrek")
    assert published == datetime(2026, 11, 2, 17, 28, 4, tzinfo=timezone.utc)


def test_missing_date():
    assert entry_published_at({}, GASGOO) is None


# ------------------------------------------------------------
# Page decoding
# ------------------------------------------------------------

def test_page_text_is_decoded_from_the_page_not_the_http_header(monkeypatch):
    html = ("<html><head><meta charset='utf-8'><title>t</title></head><body><article>"
            + "<p>智能网联汽车的发展正在加速，Google DeepMind’s planning tools help.</p>" * 20
            + "</article></body></html>").encode("utf-8")

    class Response:
        content = html
        encoding = "ISO-8859-1"          # what requests guesses without a charset header
        text = html.decode("ISO-8859-1")

    monkeypatch.setattr(feeds, "http_get", lambda url: Response())
    text = feeds.fetch_page_text("https://example.test/page")
    assert "智能网联汽车" in text
    assert "DeepMind’s" in text


# ------------------------------------------------------------
# Deduplication
# ------------------------------------------------------------

def test_canonical_url_drops_tracking_parameters_only():
    assert (canonical_url("https://x.test/a?id=3&utm_source=rss&utm_medium=feed")
            == "https://x.test/a?id=3")
    assert canonical_url("https://aidailybrief.ai/e/2026-10-29#story-2").endswith("#story-2")


def test_title_key_ignores_case_spaces_punctuation_and_invisible_characters():
    assert title_key("体系出海下半场：中国车企还需要一条数据供应链  ​") == title_key("体系出海下半场：中国车企还需要一条数据供应链")
    assert title_key("BMW: Level 2, in 2027!") == title_key("bmw level 2 in 2027")
    assert title_key("Weekly AI") is None        # too short to match on


def test_same_title_under_different_urls_is_kept_once():
    first = make_article("商用车智驾，等来了乘用车玩家", url="https://auto.gasgoo.com/news/1C601.shtml")
    second = make_article("商用车智驾，等来了乘用车玩家", url="https://auto.gasgoo.com/news/1C108.shtml")
    other = make_article("卓驭磐行发布，七大商用车品牌合作落地", url="https://auto.gasgoo.com/news/2C601.shtml")
    assert deduplicate_articles([first, second, other]) == [first, other]


def test_same_url_with_tracking_parameters_is_kept_once():
    a = make_article("First title of the article", url="https://x.test/a?utm_source=rss")
    b = make_article("A different title entirely", url="https://x.test/a")
    assert deduplicate_articles([a, b]) == [a]


def test_ai_daily_brief_stories_with_distinct_fragments_are_kept():
    stories = [make_article(f"Story number {n} headline", url=f"https://aidailybrief.ai/e/2026-10-29#s{n}")
               for n in range(3)]
    assert deduplicate_articles(stories) == stories


def test_short_generic_titles_are_not_matched():
    a = make_article("Weekly AI", url="https://a.test/1")
    b = make_article("Weekly AI", url="https://b.test/2")
    assert deduplicate_articles([a, b]) == [a, b]


# ------------------------------------------------------------
# Lookback windows and earlier digests
# ------------------------------------------------------------

def aged(title, source, hours_old):
    article = make_article(title, url=f"https://example.test/{title}")
    article.source = source
    article.published_at = datetime.now(timezone.utc) - timedelta(hours=hours_old)
    return article


def test_gasgoo_gets_a_longer_window_than_other_sources():
    articles = [aged("gasgoo-40h", GASGOO, 40), aged("gasgoo-50h", GASGOO, 50),
                aged("electrek-20h", "Electrek", 20), aged("electrek-40h", "Electrek", 40)]
    kept = [a.title for a in feeds.filter_recent_articles(articles)]
    assert kept == ["gasgoo-40h", "electrek-20h"]


def test_an_explicit_window_applies_to_every_source():
    articles = [aged("gasgoo-40h", GASGOO, 40), aged("electrek-40h", "Electrek", 40)]
    assert [a.title for a in feeds.filter_recent_articles(articles, hours=72)] == ["gasgoo-40h", "electrek-40h"]
    assert feeds.filter_recent_articles(articles, hours=24) == []


def test_articles_published_earlier_are_dropped_and_others_kept():
    old = make_article("Published yesterday already", url="https://x.test/a?utm_source=rss")
    new = make_article("Brand new article today", url="https://x.test/b")
    kept = feeds.drop_previously_published([old, new], {"https://x.test/a"})
    assert kept == [new]

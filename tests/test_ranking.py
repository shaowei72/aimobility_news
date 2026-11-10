"""Ranking policy for the market and article-type labels: roundups are
never qualified and come last among notable articles."""

from aimobility_news.config import MIN_TOTAL_SCORE
from aimobility_news.digest import generate_digest, labels
from aimobility_news.ranking import (
    NOTABLE, QUALIFIED, BELOW_THRESHOLD,
    classify_article, classify_articles, rank_articles, select_for_digest,
)

from conftest import make_article


def article(title, transport, ai, gis, article_type="news", market="US"):
    from aimobility_news.scoring import combine_scores
    return make_article(
        title,
        transport_score=transport, ai_score=ai, gis_score=gis,
        total_score=combine_scores(transport, ai, gis),
        article_type=article_type, market=market,
    )


def test_a_high_scoring_roundup_is_notable_not_qualified():
    roundup = article("Weekly roundup", 4, 4, 2, article_type="roundup")
    assert roundup.total_score >= MIN_TOTAL_SCORE
    assert classify_article(roundup) == NOTABLE
    assert classify_article(article("Same scores, news", 4, 4, 2)) == QUALIFIED


def test_a_roundup_with_no_strong_domain_is_below_threshold():
    # total 11 (qualifies as news) but no single domain reaches 3
    roundup = article("Thin roundup", 2, 2, 1, article_type="roundup")
    assert roundup.total_score >= MIN_TOTAL_SCORE
    assert classify_article(roundup) == BELOW_THRESHOLD


def test_unlabelled_articles_rank_as_before():
    # Scores stored before labels existed have article_type None
    old = article("Old score", 4, 4, 2, article_type=None, market=None)
    assert classify_article(old) == QUALIFIED
    assert labels(old) == ""


def test_roundups_come_after_qualified_and_other_notable_articles():
    roundup = article("Big roundup", 5, 5, 5, article_type="roundup")    # total 65
    qualified = article("Qualified news", 3, 3, 0)                       # total 15
    notable = article("Notable news", 0, 4, 0)                           # total 4
    ranked = classify_articles(rank_articles([notable, roundup, qualified]))

    assert [a.title for a in ranked][0] == "Big roundup"   # highest total
    published = select_for_digest(ranked, limit=3)
    assert [a.title for a in published] == ["Qualified news", "Notable news", "Big roundup"]

    # With a smaller limit the roundup is the one left out
    for a in ranked:
        a.published = False
    assert [a.title for a in select_for_digest(ranked, limit=2)] == ["Qualified news", "Notable news"]


def test_digest_shows_labels_and_lists_roundups_last(fake_llm):
    roundup = article("Big roundup", 5, 5, 5, article_type="roundup", market="Global")
    qualified = article("Qualified news", 3, 3, 0, market="Singapore", article_type="policy")
    notable = article("Notable news", 0, 4, 0)
    ranked = classify_articles(rank_articles([notable, roundup, qualified]))
    select_for_digest(ranked, limit=5)

    text = generate_digest(ranked)

    assert "**Labels:** Singapore · policy" in text
    assert "**Labels:** Global · roundup" in text
    assert text.index("Qualified news") < text.index("Notable news") < text.index("Big roundup")

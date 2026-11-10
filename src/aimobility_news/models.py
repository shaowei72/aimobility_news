from dataclasses import dataclass
from datetime import datetime
from typing import Literal

# Labels set by the scoring call (scoring.py). Policy that uses them, such as
# down-ranking roundups, lives in ranking.py, so it can change without
# re-scoring (a prompt change invalidates every stored score).
Market = Literal["Singapore", "US", "China", "Europe", "Global", "Other"]
ArticleType = Literal["news", "research", "policy", "opinion", "press_release", "roundup"]
ROUNDUP = "roundup"


@dataclass
class Article:
    title: str
    url: str
    source: str
    published_at: datetime | None
    summary: str | None
    content: str | None = None   # full article text (plain), when the feed provides it

    transport_score: int | None = None
    transport_reason: str | None = None
    ai_score: int | None = None
    ai_reason: str | None = None
    gis_score: int | None = None
    gis_reason: str | None = None
    total_score: int | None = None   # combine_scores() in scoring.py, 0-65
    market: str | None = None        # Market label, e.g. "Singapore"
    article_type: str | None = None  # ArticleType label, e.g. "roundup"
    scored_by: str | None = None     # provider:model, e.g. "ollama:qwen3.5:9b"
    scoring_error: str | None = None # set when the scoring call failed; scores stay None
    score_id: int | None = None      # scores.id in the database (db.py), set when stored or reused

    # Set by classify_articles() / select_for_digest() in ranking.py
    digest_status: str | None = None   # "qualified", "notable" or "below threshold"
    published: bool = False            # included in the published digest

    # Set by summarise_articles() in digest.py for published ITS articles
    title_en: str | None = None        # English title when the original is not in English
    digest_summary: str | None = None  # 2-3 sentence digest summary (summary above is the feed's)
    why_it_matters: str | None = None
    summarised_by: str | None = None   # provider:model
    summary_error: str | None = None   # set when the digest call failed; fields above stay None
    summary_id: int | None = None      # summaries.id in the database (db.py), set when stored or reused
    one_liner: str | None = None       # set by digest_whatsapp.add_one_liners() for WhatsApp ITS items

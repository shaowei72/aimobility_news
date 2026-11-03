from dataclasses import dataclass
from datetime import datetime


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
    scored_by: str | None = None     # provider:model, e.g. "ollama:qwen3.5:9b"
    scoring_error: str | None = None # set when the scoring call failed; scores stay None
    score_id: int | None = None      # scores.id in the database (db.py), set when stored or reused

    # Set by classify_articles() / select_for_digest() in ranking.py
    digest_status: str | None = None   # "qualified", "notable" or "below threshold"
    published: bool = False            # included in the published digest

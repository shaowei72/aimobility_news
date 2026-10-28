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

    ai_score: int | None = None
    ai_reason: str | None = None
    transport_score: int | None = None
    transport_reason: str | None = None
    total_score: int | None = None
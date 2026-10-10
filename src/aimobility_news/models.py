from dataclasses import dataclass
from datetime import datetime


@dataclass
class Article:
    title: str
    url: str
    source: str
    published_at: datetime | None
    summary: str | None

    ai_score: int | None = None
    geoai_score: int | None = None
    transport_score: int | None = None
    total_score: int | None = None
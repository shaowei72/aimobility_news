from datetime import datetime
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel

from .config import SCORING_MODEL
from .models import Article
from .scoring import text_for_scoring


client = OpenAI()

# Project root (two levels above src/aimobility_news/), so digests always
# land in <project>/output regardless of the current working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class DigestEntry(BaseModel):
    summary: str
    why_it_matters: str


def generate_article_digest(article: Article) -> DigestEntry:
    # Same capped full text (or summary) that was used for scoring
    text_label, text = text_for_scoring(article)

    prompt = f"""
You are preparing a concise daily briefing for a technically informed
reader interested in AI, GIS/GeoAI, and land transport.

For the article below:

1. Write a concise 2-3 sentence summary.
2. Write one short paragraph explaining why it matters to someone
   interested in GeoAI and land transport.

Do not exaggerate relevance. If the connection to AI, GIS, or transport
is weak, say so clearly.

Title:
{article.title}

Source:
{article.source}

{text_label}:
{text}
"""

    response = client.responses.parse(
        model=SCORING_MODEL,
        input=prompt,
        text_format=DigestEntry,
    )

    return response.output_parsed


def score_breakdown(article: Article) -> str:
    return (
        f"{article.total_score} (Transport {article.transport_score}, "
        f"AI {article.ai_score}, GIS {article.gis_score})"
    )


def append_article_entry(lines: list[str], number: int, article: Article):
    digest_entry = generate_article_digest(article)

    lines.append(f"### {number}. {article.title}")
    lines.append("")
    lines.append(f"**Source:** {article.source}")
    lines.append(f"**Score:** {score_breakdown(article)}")
    lines.append("")
    lines.append(digest_entry.summary)
    lines.append("")
    lines.append(
        f"**Why it matters:** {digest_entry.why_it_matters}"
    )
    lines.append("")
    lines.append(f"[Read article]({article.url})")
    lines.append("")


def generate_digest(
    articles: list[Article],
    also_notable: list[Article] | None = None,
) -> str:
    lines = []

    today = datetime.now().strftime("%Y-%m-%d")

    lines.append("# AI × Transport")
    lines.append(f"## Daily Briefing — {today}")
    lines.append("")

    for i, article in enumerate(articles, start=1):
        append_article_entry(lines, i, article)

    if also_notable:
        lines.append("## Also notable (strong in one domain)")
        lines.append("")

        for i, article in enumerate(also_notable, start=len(articles) + 1):
            append_article_entry(lines, i, article)

    return "\n".join(lines)


def generate_debug_digest(
    ranked_articles: list[Article],
    selected: list[Article],
    also_notable: list[Article],
    min_total_score: int,
) -> str:
    # Every scored article with its scores and reasons, for tuning the rubric
    # and threshold. No LLM calls: only scoring output is shown.
    selected_urls = {article.url for article in selected}
    notable_urls = {article.url for article in also_notable}

    def status(article: Article) -> str:
        if article.url in selected_urls:
            return "selected"
        if article.url in notable_urls:
            return "also notable"
        if (article.total_score or 0) >= min_total_score:
            return "qualified, over Top N"
        return "below threshold"

    lines = []

    today = datetime.now().strftime("%Y-%m-%d")

    lines.append("# AI × Transport — Debug")
    lines.append(f"## All scored articles — {today}")
    lines.append("")
    lines.append(
        f"{len(ranked_articles)} scored, {len(selected)} selected, "
        f"{len(also_notable)} also notable, "
        f"MIN_TOTAL_SCORE = {min_total_score}"
    )
    lines.append("")

    lines.append(
        "| # | Status | Total | Transport | AI | GIS | Source | Title |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")

    for i, article in enumerate(ranked_articles, start=1):
        title = article.title.replace("|", "\\|")
        lines.append(
            f"| {i} | {status(article)} | {article.total_score} "
            f"| {article.transport_score} | {article.ai_score} "
            f"| {article.gis_score} | {article.source} | {title} |"
        )

    lines.append("")

    for i, article in enumerate(ranked_articles, start=1):
        text_label, text = text_for_scoring(article)
        words = len(text.split()) if text else 0

        lines.append(f"### {i}. {article.title}")
        lines.append("")
        lines.append(f"**Status:** {status(article)}")
        lines.append(f"**Source:** {article.source}")
        lines.append(f"**Published:** {article.published_at}")
        lines.append(f"**Scored on:** {text_label} ({words} words)")
        lines.append(f"**Score:** {score_breakdown(article)}")
        lines.append("")
        lines.append(f"**Transport reason:** {article.transport_reason}")
        lines.append("")
        lines.append(f"**AI reason:** {article.ai_reason}")
        lines.append("")
        lines.append(f"**GIS reason:** {article.gis_reason}")
        lines.append("")
        lines.append(f"[Read article]({article.url})")
        lines.append("")

    return "\n".join(lines)


def save_digest(
    digest: str,
    output_dir: Path = PROJECT_ROOT / "output",
    prefix: str = "digest",
) -> Path:
    output_path = Path(output_dir)

    output_path.mkdir(exist_ok=True)

    base_name = f"{prefix}-{datetime.now():%Y-%m-%d}"
    file_path = output_path / f"{base_name}.md"

    counter = 1

    while file_path.exists():
        file_path = output_path / f"{base_name}({counter}).md"
        counter += 1

    file_path.write_text(digest, encoding="utf-8")

    return file_path
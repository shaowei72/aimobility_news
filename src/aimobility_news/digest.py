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



def generate_digest(articles: list[Article]) -> str:
    lines = []

    today = datetime.now().strftime("%Y-%m-%d")

    lines.append("# AI × Transport")
    lines.append(f"## Daily Briefing — {today}")
    lines.append("")

    for i, article in enumerate(articles, start=1):
        digest_entry = generate_article_digest(article)

        lines.append(f"### {i}. {article.title}")
        lines.append("")
        lines.append(f"**Source:** {article.source}")
        lines.append(f"**Score:** {article.total_score}")
        lines.append("")
        lines.append(digest_entry.summary)
        lines.append("")
        lines.append(
            f"**Why it matters:** {digest_entry.why_it_matters}"
        )
        lines.append("")
        lines.append(f"[Read article]({article.url})")
        lines.append("")

    return "\n".join(lines)

def save_digest(
    digest: str,
    output_dir: Path = PROJECT_ROOT / "output"
) -> Path:
    output_path = Path(output_dir)

    output_path.mkdir(exist_ok=True)

    base_name = f"digest-{datetime.now():%Y-%m-%d}"
    file_path = output_path / f"{base_name}.md"

    counter = 1

    while file_path.exists():
        file_path = output_path / f"{base_name}({counter}).md"
        counter += 1

    file_path.write_text(digest, encoding="utf-8")

    return file_path
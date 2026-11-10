"""WhatsApp-ready digest (v0.5): a compact plain-text version of the Daily
Briefing for manual copy/paste into WhatsApp.

- ITS items: the published articles (qualified, then "Also notable"), each
  with a one-line summary derived from its digest summary. All one-liners
  come from one LLM call; if it fails, each falls back to the first sentence
  of the summary.
- AI Daily Brief items: the story headline, which is already one line, so
  no LLM call.

Uses WhatsApp's own formatting (*bold*, _italic_) and bare links, since
WhatsApp does not render Markdown links. Length is set in config.py
(WHATSAPP_*). main.py saves the text to output/whatsapp-YYYY-MM-DD.txt and,
if WHATSAPP_COPY_TO_CLIPBOARD, puts it on the Windows clipboard; sending it
is manual.
"""

import re
import subprocess
import sys
from datetime import datetime

from pydantic import BaseModel

from . import llm
from .config import (
    WHATSAPP_MAX_ITS,
    WHATSAPP_MAX_AIDB,
    WHATSAPP_INCLUDE_NOTABLE,
    WHATSAPP_ONE_LINERS,
)
from .models import Article
from .ranking import QUALIFIED, NOTABLE, digest_order


class OneLiner(BaseModel):
    number: int
    line: str


class OneLiners(BaseModel):
    lines: list[OneLiner]


# ------------------------------------------------------------
# Selection
# ------------------------------------------------------------

def select_its_items(ranked_articles: list[Article]) -> list[Article]:
    # Same order as the Markdown digest: qualified first, then notable
    statuses = (QUALIFIED, NOTABLE) if WHATSAPP_INCLUDE_NOTABLE else (QUALIFIED,)
    # digest_order(): qualified first, then notable with roundups last
    published = [a for a in digest_order(ranked_articles)
                 if a.published and a.digest_status in statuses]
    return published[:WHATSAPP_MAX_ITS]


# ------------------------------------------------------------
# One-line summaries
# ------------------------------------------------------------

def first_sentence(text: str | None, max_chars: int = 220) -> str | None:
    if not text:
        return None
    sentence = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]
    if len(sentence) > max_chars:
        sentence = sentence[:max_chars].rsplit(" ", 1)[0] + "…"
    return sentence


def one_liner_prompt(articles: list[Article]) -> str:
    items = "\n\n".join(
        f"{n}. Title: {a.title_en or a.title}\n"
        f"Summary: {a.digest_summary}\n"
        f"Why it matters: {a.why_it_matters}"
        for n, a in enumerate(articles, start=1)
    )
    return f"""
You are condensing a daily news briefing for a WhatsApp message to a
technically informed reader interested in AI, GIS/GeoAI and land transport.

For each numbered item below, write one line (at most 25 words) giving the
single most important fact or development. Be concrete (who, what, numbers),
do not repeat the title word for word, do not exaggerate, and write plain
English text without asterisks, underscores or emoji.

Return one line per item, with the item's number.

{items}
"""


def add_one_liners(articles: list[Article]) -> list[Article]:
    """Set article.one_liner for each article with a digest summary, using
    one LLM call; on failure (or a missing line) fall back to the first
    sentence of the summary."""
    summarised = [a for a in articles if a.digest_summary]
    lines = {}
    if summarised:
        try:
            result = llm.parse(one_liner_prompt(summarised), OneLiners,
                               task="digest", label="WhatsApp one-liners")
            lines = {item.number: item.line.strip() for item in result.lines}
        except Exception as e:
            print(f"WARNING: WhatsApp one-liners failed, using first sentences: "
                  f"{type(e).__name__}: {e}")

    for n, article in enumerate(summarised, start=1):
        article.one_liner = lines.get(n) or first_sentence(article.digest_summary)
    return articles


# ------------------------------------------------------------
# Formatting
# ------------------------------------------------------------

def clean(text: str) -> str:
    # WhatsApp formatting characters inside a title or line would turn
    # parts of it bold, italic, struck through or monospace
    return re.sub(r"[*_~`]", "", text).strip()


def generate_whatsapp(its_items: list[Article], ai_items: list[Article],
                      day: datetime | None = None) -> str:
    day = day or datetime.now()
    lines = [f"*Daily Briefing — {day.day} {day:%b %Y}*", ""]

    lines += ["*🚦 Intelligent Transport (ITS)*", ""]
    if not its_items:
        lines += ["_No ITS articles today._", ""]
    for n, article in enumerate(its_items, start=1):
        lines.append(f"{n}. *{clean(article.title_en or article.title)}*")
        if article.one_liner:
            lines.append(clean(article.one_liner))
        lines += [article.url, ""]

    lines += ["*🤖 AI Daily Brief*", ""]
    if not ai_items:
        lines += ["_No AI Daily Brief stories today._", ""]
    for n, article in enumerate(ai_items, start=1):
        lines += [f"{n}. *{clean(article.title)}*", article.url, ""]

    return "\n".join(lines).rstrip() + "\n"


def build_whatsapp(ranked_articles: list[Article], ai_headlines: list[Article]) -> str:
    its_items = select_its_items(ranked_articles)
    if WHATSAPP_ONE_LINERS:
        add_one_liners(its_items)
    return generate_whatsapp(its_items, ai_headlines[:WHATSAPP_MAX_AIDB])


# ------------------------------------------------------------
# Clipboard
# ------------------------------------------------------------

def copy_to_clipboard(text: str) -> bool:
    """Put the text on the Windows clipboard (clip.exe reads UTF-16LE, so
    emoji and accented characters survive). Returns False if not possible."""
    if sys.platform != "win32":
        print("WARNING: clipboard copy is only supported on Windows")
        return False
    try:
        subprocess.run(["clip"], input=text.replace("\n", "\r\n").encode("utf-16-le"),
                       check=True, timeout=10)
        return True
    except (OSError, subprocess.SubprocessError) as e:
        print(f"WARNING: could not copy to the clipboard: {type(e).__name__}: {e}")
        return False

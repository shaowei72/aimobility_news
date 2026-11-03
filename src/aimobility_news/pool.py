"""Candidate pool for the evaluation dataset (v0.3 step 4).

Every run appends its scored articles to a JSON Lines file, one article per
line, with the exact text the model scored and its scores and reasons. The
evaluation set is later picked from this pool; v0.4 can import it into SQLite.
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import llm
from .config import SCORED_POOL, MIN_TOTAL_SCORE, MAX_CONTENT_WORDS
from .models import Article
from .scoring import text_for_scoring
from .textlen import text_length


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def code_version() -> str | None:
    # Short git commit, so a pool entry can be traced to the rubric that
    # produced it ("+dirty" when there were uncommitted changes)
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        return f"{commit}+dirty" if dirty else commit
    except (OSError, subprocess.CalledProcessError):
        return None


def pool_record(article: Article, run_info: dict) -> dict:
    text_label, text = text_for_scoring(article)
    return {
        **run_info,
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        # Exactly what the model was given, so the article can be rescored
        # without refetching
        "text_label": text_label,
        "text": text,
        "text_words": text_length(text),
        "has_full_text": bool(article.content),
        "scored_by": article.scored_by,
        "scoring_error": article.scoring_error,
        "transport_score": article.transport_score,
        "transport_reason": article.transport_reason,
        "ai_score": article.ai_score,
        "ai_reason": article.ai_reason,
        "gis_score": article.gis_score,
        "gis_reason": article.gis_reason,
        "total_score": article.total_score,
        "digest_status": article.digest_status,
        "published": article.published,
    }


def save_to_pool(articles: list[Article]) -> Path | None:
    if not SCORED_POOL or not articles:
        return None

    run_info = {
        "run_id": llm.RUN_ID,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code_version": code_version(),
        "min_total_score": MIN_TOTAL_SCORE,
        "max_content_words": MAX_CONTENT_WORDS,
    }

    path = PROJECT_ROOT / SCORED_POOL
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for article in articles:
                f.write(json.dumps(pool_record(article, run_info), ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"WARNING: could not write scored-article pool {path}: {e}")
        return None

    return path

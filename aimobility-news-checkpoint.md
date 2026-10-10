# AI Mobility News App — Checkpoint

_Last updated: 2026-10-10_

## Project name

`aimobility-news`  
Python package: `aimobility_news`  
Local folder: `E:\MyLocalDev\AIMobility\aimobility_news`  
Remote: https://github.com/shaowei72/aimobility_news

## Goal

Build a daily AI-powered news intelligence app focused on:

- GeoAI / GIS
- AI applied to land transport
- Developments relevant to transport authorities, operators, planners, and geospatial teams

## MVP scope

The first version should:

- [x] Collect recent articles from a small set of RSS feeds
- [x] Normalise them into a common article structure
- [x] Deduplicate
- [x] Score relevance
- [x] Rank and select a Top 5
- [ ] Generate a WhatsApp-friendly digest (a Markdown digest exists; not yet WhatsApp-formatted)
- [ ] Store articles and scores in SQLite
- [x] Save the daily digest as Markdown

For now, agent frameworks, RAG, vector databases, advanced UI, and automatic WhatsApp sending remain out of scope.

## Current project structure

```text
aimobility_news/
├── .gitignore
├── pyproject.toml
├── README.md
├── uv.lock
├── aimobility-news-checkpoint.md
├── .venv/                      (local only, git-ignored)
├── output/                     (generated digests; currently untracked, not git-ignored)
│   └── digest-2026-10-10.md
└── src/
    └── aimobility_news/
        ├── __init__.py
        ├── config.py           # FEEDS, RECENT_HOURS, SCORING_MODEL
        ├── models.py           # Article dataclass (+ score fields)
        ├── feeds.py            # fetch, filter recent, deduplicate
        ├── scoring.py          # OpenAI relevance scoring; currently also runs the full pipeline
        ├── ranking.py          # sort by total_score
        ├── digest.py           # OpenAI summaries -> Markdown digest -> output/
        ├── openAI.py           # scratch script: list available gpt-6 models
        └── validate_feeds.py   # feed health check
```

## Environment setup

- `uv` 0.12.24 installed
- Python 3.11.1 (`requires-python = ">=3.10"`)
- Virtual environment created with `uv sync`
- Corporate TLS issue resolved by telling uv to use the Windows/system certificate store:

```powershell
uv sync --system-certs
uv add <package> --system-certs
```

- Older `--native-tls` flag is deprecated in current uv; use `--system-certs`

Declared dependencies (`pyproject.toml`):

- `feedparser>=6.0.14`
- `openai>=3.28.0`

`pydantic` is imported by `scoring.py` and `digest.py` but is **not declared**; it is only installed because `openai` depends on it. Add it explicitly:

```powershell
uv add pydantic --system-certs
```

OpenAI credentials: the client reads `OPENAI_API_KEY` from the environment. `.env` / `.env.*` are git-ignored; no keys are in the repository.

## Repository housekeeping

- Git repository on `main`, pushed to GitHub (`origin`)
- `.gitignore` covers virtual environments, caches, secrets, logs, OS files, build artefacts, and `*.egg-info/`
- Previously tracked `src/aimobility_news.egg-info/` was removed from Git tracking
- Commit history:
  - `c8821e7` Fix article date handling and guard validate_feeds script
  - `0a594a6` Add recent-article filtering, deduplication, and OpenAI relevance scoring
- **Uncommitted as of this checkpoint:** `config.py` (`SCORING_MODEL`), `scoring.py` (rubric, product scoring, pipeline), new `ranking.py`, new `digest.py`, and `output/`

## RSS validation

`validate_feeds.py` tests the configured RSS feeds and reports, per feed:

- HTTP status
- Whether parsing failed (`feedparser`'s `bozo` flag)
- Number of entries
- Error details if parsing failed
- Latest article title, publication date, and link

Its logic lives in a `validate_feeds()` function behind an `if __name__ == "__main__":` guard, so importing the module has no side effects (no network calls, no printing).

Run as a package module:

```powershell
uv run python -m aimobility_news.validate_feeds
```

All modules must be run with `-m` because the package uses relative imports (`from .config import FEEDS`). Running a file directly by path causes:

```text
ImportError: attempted relative import with no known parent package
```

## Shared configuration

`src/aimobility_news/config.py` is the single source of truth:

```python
FEEDS = { ... }                   # 6 RSS feeds
RECENT_HOURS = 48                 # time window for filter_recent_articles()
SCORING_MODEL = "gpt-6.1-sol"     # used by scoring.py and digest.py
```

## Current feed set and validation results

### Keep

**GIM International**

```text
HTTP status: 301
Parse error: False
Entries: 100
Latest: PwC and Esri to harness geospatial AI together
Result: OK
```

**Geospatial World**

```text
HTTP status: 301
Parse error: False
Entries: 10
Result: OK
```

**Open Geospatial Consortium**

```text
HTTP status: 301
Parse error: False
Entries: 10
Result: OK
```

### Keep for now

**QGIS Blog**

```text
HTTP status: 301
Parse error: False
Entries: 10
Result: OK
```

**Planet OSGeo**

```text
HTTP status: 301
Parse error: True
Entries: 40
Error: document declared as us-ascii, but parsed as utf-8
Result: WARN
```

The warning is non-fatal because entries are still returned.

**Smart Cities Dive**

```text
HTTP status: 200
Parse error: False
Entries: 10
Result: OK
```

This feed is broad and may contain irrelevant items, which is useful for testing AI relevance filtering.

### Drop / revisit later

**Esri ArcGIS Blog**

```text
HTTP status: 403
Entries: 0
Result: FAIL
```

**ITS International**

```text
HTTP status: 404
Entries: 0
Result: FAIL
```

**Sustainable Bus - ITS**

```text
HTTP status: 301
Parse error: True
Entries: 0
Result: FAIL
```

**Railway Gazette - Metro**

```text
HTTP status: 404
Parse error: True
Entries: 0
Result: FAIL
```

## Key source-design learnings

A valuable news source does not necessarily have a usable RSS feed. Sources such as Esri or ITS International may still be useful later through another ingestion method.

The current source mix is stronger on GIS/geospatial than land transport, and stronger land-transport feeds are needed.

**New (2026-10-10): feed freshness is now the main bottleneck.** On 2026-10-10, 180 articles were fetched, but only **6** fell within the 48-hour window — and **all 6 were from Smart Cities Dive**. The geospatial feeds publish infrequently (e.g. many GIM International items are weeks or months old). As a result, the first digest's Top 5 were all Smart Cities Dive housing/funding stories with scores of 1–5 out of 125. Adding more, and more frequently updated, sources matters more right now than tuning the scoring.

## Article data model

`src/aimobility_news/models.py`:

```python
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
```

`Article` is the common application-level representation of a news item, so downstream code does not need to know which RSS source an article came from. Score fields default to `None` and are filled in by `scoring.py`.

## Pipeline

```text
fetch_articles()            feeds.py    RSS -> Article objects
→ filter_recent_articles()  feeds.py    keep last RECENT_HOURS (48h)
→ deduplicate_articles()    feeds.py    by exact URL
→ score_articles()          scoring.py  OpenAI: ai / geoai / transport scores
→ rank_articles()           ranking.py  sort by total_score, descending
→ [:5]                                  Top 5
→ generate_digest()         digest.py   OpenAI summary + "why it matters" per article
→ save_digest()             digest.py   output/digest-YYYY-MM-DD.md
```

Currently run end-to-end via:

```powershell
uv run python -m aimobility_news.scoring
```

First successful end-to-end run: 2026-10-10, producing `output/digest-2026-10-10.md`.

### Ingestion (`feeds.py`)

- `fetch_articles()` loops over `FEEDS`, parses each with `feedparser`, and converts entries to `Article`.
- `published_at` is reset to `None` for every entry, then set from `published_parsed` (UTC) when available. (Bug fixed: previously the value leaked from the previous entry or raised `NameError`.)
- `filter_recent_articles(articles, hours=RECENT_HOURS)` keeps articles with `published_at >= now - hours`. **Articles with no publication date are dropped.**
- `deduplicate_articles(articles)` keeps the first article for each exact URL.
- `__main__` block prints counts and a random sample of up to 10 articles (`min(10, len(...))`).

### Scoring (`scoring.py`)

- Uses OpenAI structured output (`client.responses.parse` with a pydantic `ArticleScore` model) on the title and RSS summary.
- Three criteria, each an integer 1–5 using a rubric (1 = not/weakly relevant … 5 = central to the article):
  - `ai_score` — artificial intelligence
  - `geoai_score` — GIS, geospatial, spatial analytics, mapping, digital twins, GeoAI
  - `transport_score` — land transport: roads, rail, buses, traffic, mobility, planning, operations
- `total_score = ai_score * geoai_score * transport_score` (range 1–125). This was changed from a sum (range 0–15). The product rewards articles that hit **all three** themes; an article strong in only one theme scores low (e.g. 5×1×1 = 5, while 3×3×3 = 27).
- One API call per article, made sequentially.

### Ranking (`ranking.py`)

- `rank_articles()` sorts by `total_score` descending (treating `None` as 0).

### Digest (`digest.py`)

- `generate_article_digest()` asks the model for a 2–3 sentence summary and a "why it matters" paragraph (pydantic `DigestEntry`), instructed not to exaggerate relevance.
- `generate_digest()` builds Markdown: a header with the date, then for each article its title, source, score, summary, why it matters, and link.
- `save_digest()` writes `output/digest-YYYY-MM-DD.md` (overwrites if run twice on the same day).

### Scratch

- `openAI.py` lists available model IDs containing `gpt-6`. It runs on import and is not part of the pipeline; delete it or move it out of the package eventually.

## Review findings (2026-10-10)

Correctness / robustness:

1. **No relevance threshold.** The Top 5 is always filled even if every article scores 1; the first digest contained housing and FEMA stories. Consider a minimum `total_score` (or minimum per-criterion score) and allowing fewer than 5 items.
2. **No error handling around OpenAI calls.** One failed or rate-limited request aborts the whole run, losing all scores already paid for. Add try/except with retry, or skip failed articles.
3. **Module-level `client = OpenAI()`** in `scoring.py` and `digest.py`: importing either module fails if `OPENAI_API_KEY` is unset (the same "side effects on import" issue that was fixed in `validate_feeds.py`). Create the client lazily or inside functions.
4. **Undated articles are silently dropped** by `filter_recent_articles()`. That is fine for today's feeds (all entries had dates), but it should be a conscious decision.
5. **RSS summaries may contain HTML**, which is sent to the model as-is. It works, but costs tokens; consider stripping tags.

Structure / housekeeping:

6. **Pipeline orchestration lives in `scoring.py`'s `__main__`**, so `scoring.py` imports `feeds`, `ranking`, and `digest`. Move it to a dedicated entry point (e.g. `main.py` or `pipeline.py`, run with `uv run python -m aimobility_news.main`, or a `[project.scripts]` entry).
7. **`pydantic` is not declared** in `pyproject.toml` (see Environment setup).
8. **`feeds.py` prints "Published in last 24 hours"** but `RECENT_HOURS` is 48; use an f-string with `RECENT_HOURS`.
9. **`output/` is neither tracked nor git-ignored.** Decide whether digests belong in the repository; if not, add `output/` to `.gitignore`.
10. Large blocks of commented-out test code in `feeds.py` and `scoring.py`; these would be better as real tests (e.g. pytest with hand-built `Article` objects for `filter_recent_articles`, `deduplicate_articles`, `rank_articles`).
11. Minor style: double space in `random.sample(unique_articles,  min(...))`; `ai_score*article.geoai_score *article.transport_score` spacing; several files lack a trailing newline.

Cost note: each run makes N scoring calls (N = recent unique articles) plus 5 digest calls. With 6 recent articles that is small, but it grows with more feeds or a wider window.

## Current stage

The MVP pipeline runs end-to-end and produces a Markdown digest.

Completed:

```text
environment setup
→ feed validation
→ shared configuration
→ Article model
→ RSS ingestion + publication date parsing
→ recent-article filtering (48h)
→ URL deduplication
→ OpenAI relevance scoring (3 criteria, product total)
→ ranking + Top 5
→ Markdown digest generation and saving
```

Not yet done:

```text
SQLite storage of articles and scores
WhatsApp-friendly digest formatting
dedicated pipeline entry point
tests
```

## Next steps

Suggested order:

1. **Commit the current work** (`config.py`, `scoring.py`, `ranking.py`, `digest.py`) and decide on `output/` (track vs. git-ignore).
2. **Improve source coverage and freshness** — add more frequently updated land-transport and GeoAI feeds; this currently limits digest quality more than anything else.
3. **Add a relevance threshold** so irrelevant articles do not fill the Top 5.
4. **Move the pipeline into a `main.py` entry point** and make OpenAI client creation lazy.
5. **Add error handling/retries** around OpenAI calls.
6. **SQLite storage** of articles and scores (also enables skipping already-scored URLs across runs, saving API cost).
7. **WhatsApp-friendly digest** format (plain text, short lines, no Markdown headers).

## Resume point

The pipeline works end-to-end. Resume by **committing the uncommitted scoring/ranking/digest work**, then **expanding and refreshing the feed list** and **adding a relevance threshold** so the daily Top 5 is actually on-topic.

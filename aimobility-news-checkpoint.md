# AI Mobility News App — Checkpoint

_Last updated: 2026-10-10 — MVP v0.1 complete_

## Project

`aimobility-news`  
Python package: `aimobility_news`  
Local folder: `E:\MyLocalDev\AIMobility\aimobility_news`  
Remote: https://github.com/shaowei72/aimobility_news

**Goal:** a daily AI-powered news intelligence digest focused on GeoAI / GIS, AI applied to land transport, and developments relevant to transport authorities, operators, planners, and geospatial teams.

Not in scope until later roadmap versions: web UI (v0.5), embeddings / vector databases / RAG (v0.6), and agentic research (v0.7). Automatic WhatsApp sending is not yet planned; v0.4 covers copy/paste-ready output only.

---

## 1. MVP v0.1 — complete

- [x] RSS ingestion
- [x] Recent-article filtering
- [x] Deduplication
- [x] AI relevance scoring
- [x] Ranking and Top 5
- [x] AI-generated summary + "why it matters"
- [x] Markdown digest output

Run the full pipeline:

```powershell
uv run python -m aimobility_news.main
```

First successful end-to-end run: 2026-10-10 → `output/digest-2026-10-10.md`.

Released in commit `8a47bfa` ("Build MVP v0.1 for AI mobility news digest"), followed by `b10c490` (scoring.py `__main__` reduced to a single-article test).

---

## 2. Key learnings from v0.1

- **Feed freshness is a major constraint.** On 2026-10-10, 180 articles were fetched but only 6 fell inside the 48-hour window, and all 6 came from Smart Cities Dive. The geospatial feeds publish infrequently (many GIM International items are weeks or months old).
- **The source mix is stronger in GIS than land transport.** None of the current feeds is transport-focused; the candidate transport feeds (ITS International, Sustainable Bus, Railway Gazette) all failed validation.
- **Relevance scoring works well enough for MVP.** The model scored off-topic housing and FEMA funding stories at 1–5 out of 125 and explained the weak relevance honestly in the digest.
- **The pipeline is functional end-to-end**: fetch → filter → deduplicate → score → rank → Top 5 → digest → Markdown.
- **Output quality now depends more on source quality and thresholding than on pipeline mechanics.** The first digest's Top 5 was filled with low-relevance articles because there were few fresh candidates and no minimum score.

---

## 3. Next extensions (priority order)

### 1. Source coverage and freshness

- Add stronger land-transport feeds
- Find more frequently updated GeoAI sources
- Possibly add non-RSS ingestion later (e.g. for Esri, ITS International)

### 2. Relevance thresholding

- Allow fewer than 5 items if only a few are genuinely relevant
- Tune the product-score threshold based on daily runs

### 3. SQLite repository

- Store article metadata, scores, dates, source, and digest status
- Avoid rescoring articles already seen (saves API cost)
- Create the foundation for historical search

### 4. WhatsApp-friendly output

- Produce compact plain-text formatting
- Shorter summaries
- Easy copy/paste

### 5. Robustness

- Retry failed API calls (currently one failure aborts the whole run)
- Handle feed errors gracefully
- Strip HTML from RSS summaries
- Create the OpenAI client lazily instead of at import time in `scoring.py` and `digest.py` (importing currently fails without `OPENAI_API_KEY`)

### 6. Testing and cleanup

- ~~Move orchestration into `main.py`~~ — done (`main.py` added; `scoring.py` `__main__` is now a single-article test)
- Add proper unit tests (e.g. pytest with hand-built `Article` objects for filtering, deduplication, ranking)
- Remove scratch code: `openAI.py`, commented-out test block in `feeds.py`
- Declare `pydantic` in `pyproject.toml` (`uv add pydantic --system-certs`); it is used directly but only installed via `openai`
- Fix the `feeds.py` message "Published in last 24 hours" — `RECENT_HOURS` is 48
- Decide on `output/`: track generated digests in Git, or add it to `.gitignore` (currently untracked)

---

## 4. Roadmap

```text
v0.1  MVP pipeline                      ✅ complete
v0.2  better sources + thresholding
v0.3  SQLite repository
v0.4  WhatsApp-ready digest
v0.5  searchable web interface
v0.6  embeddings / RAG
v0.7  agentic research
```

Robustness (extension 5) and testing/cleanup (extension 6) are ongoing work alongside each release rather than separate versions.

---

## Reference

### Project structure

```text
aimobility_news/
├── .gitignore
├── pyproject.toml
├── README.md
├── uv.lock
├── aimobility-news-checkpoint.md
├── .venv/                      (local only, git-ignored)
├── output/                     (generated digests; untracked, not git-ignored)
└── src/
    └── aimobility_news/
        ├── __init__.py
        ├── main.py             # pipeline entry point
        ├── config.py           # FEEDS, RECENT_HOURS, SCORING_MODEL
        ├── models.py           # Article dataclass (+ score fields)
        ├── feeds.py            # fetch, filter recent, deduplicate
        ├── scoring.py          # OpenAI relevance scoring
        ├── ranking.py          # sort by total_score
        ├── digest.py           # OpenAI summaries -> Markdown digest -> output/
        ├── openAI.py           # scratch: list available gpt-6 models
        └── validate_feeds.py   # feed health check
```

### Environment

- `uv` 0.12.24, Python 3.11.1 (`requires-python = ">=3.10"`)
- Corporate TLS: use the system certificate store (`--native-tls` is deprecated):

```powershell
uv sync --system-certs
uv add <package> --system-certs
```

- Declared dependencies: `feedparser>=6.0.14`, `openai>=3.28.0`
- OpenAI credentials come from the `OPENAI_API_KEY` environment variable. `.env` / `.env.*` are git-ignored; no keys are in the repository.
- All modules must be run with `-m` (e.g. `uv run python -m aimobility_news.main`) because the package uses relative imports; running a file by path raises `ImportError: attempted relative import with no known parent package`.

### Configuration (`config.py`)

```python
FEEDS = { ... }                   # 6 RSS feeds
RECENT_HOURS = 48                 # time window for filter_recent_articles()
SCORING_MODEL = "gpt-6.1-sol"     # used by scoring.py and digest.py
```

### Pipeline

```text
fetch_articles()            feeds.py    RSS -> Article objects
→ filter_recent_articles()  feeds.py    keep last RECENT_HOURS (48h); undated articles dropped
→ deduplicate_articles()    feeds.py    by exact URL
→ score_articles()          scoring.py  OpenAI: ai / geoai / transport scores
→ rank_articles()           ranking.py  sort by total_score, descending
→ [:5]                      main.py     Top 5
→ generate_digest()         digest.py   OpenAI summary + "why it matters" per article
→ save_digest()             digest.py   output/digest-YYYY-MM-DD.md (overwrites same day)
```

**Scoring:** OpenAI structured output (`client.responses.parse` with pydantic `ArticleScore`) on the title and RSS summary. Three criteria, each an integer 1–5 (1 = not/weakly relevant … 5 = central to the article):

- `ai_score` — artificial intelligence
- `geoai_score` — GIS, geospatial, spatial analytics, mapping, digital twins, GeoAI
- `transport_score` — land transport: roads, rail, buses, traffic, mobility, planning, operations

`total_score = ai_score × geoai_score × transport_score` (range 1–125). The product rewards articles that hit all three themes; an article strong in one theme only scores low (5×1×1 = 5 vs 3×3×3 = 27).

**Cost:** one scoring call per recent unique article, plus 5 digest calls per run.

### Article model (`models.py`)

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

### Feed status

Validate with `uv run python -m aimobility_news.validate_feeds`.

| Feed | Status | Notes |
|---|---|---|
| GIM International | OK — keep | 100 entries, but mostly old |
| Geospatial World | OK — keep | 10 entries |
| Open Geospatial Consortium | OK — keep | 10 entries |
| QGIS Blog | OK — keep for now | 10 entries |
| Planet OSGeo | WARN — keep for now | 40 entries; non-fatal encoding warning (us-ascii declared, utf-8 parsed) |
| Smart Cities Dive | OK — keep for now | 10 entries; broad, frequently updated, often off-topic |
| Esri ArcGIS Blog | FAIL (403) — dropped | Revisit via non-RSS ingestion |
| ITS International | FAIL (404) — dropped | Revisit via non-RSS ingestion |
| Sustainable Bus - ITS | FAIL (0 entries) — dropped | |
| Railway Gazette - Metro | FAIL (404) — dropped | |

A valuable news source does not necessarily have a usable RSS feed.

### Commit history

```text
b10c490 Reduce scoring.py __main__ to a single-article test
8a47bfa Build MVP v0.1 for AI mobility news digest
da2b07e Add ranking and Markdown digest generation; update checkpoint
0a594a6 Add recent-article filtering, deduplication, and OpenAI relevance scoring
c8821e7 Fix article date handling and guard validate_feeds script
596d391 Remove egg-info build artifacts and add project checkpoint notes
a6914ad Add .gitignore
ea73049 My first commit
```

---

## Resume point

MVP v0.1 is complete. Start v0.2 with **extension 1: source coverage and freshness** — find and validate stronger land-transport feeds and more frequently updated GeoAI sources — then add **relevance thresholding** so the daily digest contains only genuinely relevant items.

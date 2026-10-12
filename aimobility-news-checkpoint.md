# AI Mobility News App — Checkpoint

_Last updated: 2026-10-12 — MVP v0.2 in progress_

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

Released in commit `8a47bfa` ("Build MVP v0.1 for AI mobility news digest"), followed by `b10c490` (`scoring.py` `__main__` reduced to a single-article test).

---

## 2. MVP v0.2 — progress so far

The main focus of v0.2 is **better source coverage and freshness** plus **relevance thresholding**. The thresholding mechanism is now implemented; remaining work is mainly source validation, end-to-end testing, and threshold tuning.

### 2.1 Esri non-RSS ingestion — working

Esri remains strategically important, but direct access proved difficult:

```text
RSS feed
→ 403 / unusable

requests + BeautifulSoup
→ 403 Forbidden

Playwright / Chromium
→ Access Denied

OpenAI web search
→ works
```

A new `esri_search.py` module now uses the OpenAI Responses API with the web-search tool to find recent ArcGIS Blog content and convert results into the common `Article` model.

The main pipeline can combine sources before applying the existing downstream logic:

```text
RSS sources -----------\
                       \
Esri search ------------→ Article objects
                       /
Other source adapters -/

→ recent filter
→ deduplicate
→ score
→ rank
→ digest
```

A timezone mismatch was found when combining Esri and RSS results (`offset-naive` vs `offset-aware` datetimes). Esri dates are now normalized to timezone-aware UTC datetimes.

A full pipeline run successfully returned 10 Esri articles, but none survived the normal 48-hour freshness filter because the newest Esri result was older than 48 hours. This showed that the Esri ingestion path works, while also highlighting the need to separate **source availability** from **daily freshness**.

### 2.2 More robust RSS retrieval — validated on Substack

Direct `feedparser.parse(url)` failed on the GeoAI Signal Substack feed even though the server returned HTTP 200. The feed reported a malformed XML error and zero entries.

A more robust pattern was tested successfully:

```text
requests.get(url)
→ response.content
→ feedparser.parse(response.content)
```

Using this approach, GeoAI Signal returned:

```text
HTTP status: 200
Parse error: False
Entries: 9
```

This suggests that `requests` should handle HTTP retrieval and `feedparser` should focus on RSS parsing. The pattern should be used consistently in `feeds.py` and `validate_feeds.py`.

`feeds.py` now uses this pattern via `load_feed()`. `validate_feeds.py` still calls `feedparser.parse(url)` directly, so its results can differ from what the pipeline actually fetches — still to be switched over.

Note: `load_feed()` calls `raise_for_status()` and `fetch_articles()` does not catch errors, so a single failing feed (403, timeout) now aborts the whole run. Previously `feedparser.parse(url)` never raised.

GeoAI Signal is a strong GeoAI source, but it publishes roughly weekly, so it will only enter a 24-hour digest shortly after publication.

Additional Substack sources, now added to `FEEDS`:

- GeoAI Unpacked — `/feed`
- Geospatial Law — `/feed`; adjacent governance / policy source

### 2.3 AI Daily Brief direct scraping — implemented and refined

`aidailybrief.ai` does not currently have a verified RSS endpoint, but its archive page is directly accessible and structured enough to scrape.

A new `aidailybrief.py` source adapter uses `requests + BeautifulSoup` and converts editions into `Article` objects.

The first scraper version picked up the wrong `/e/...` links and failed to extract useful summaries. HTML inspection identified the correct archive structure:

```text
.ed-main
├── .ed-kicker
├── .ed-title     ← edition title
└── .ed-teaser    ← summary / teaser
```

The scraper should therefore select only `a.ed-title` links and extract the summary from the enclosing `.ed-main .ed-teaser` block.

For v0.2, one AI Daily Brief edition is treated as one `Article`. Splitting each edition into individual stories can be considered later if finer-grained ranking is needed.

### 2.4 Singapore mainstream news sources added

The Straits Times and The Business Times both expose RSS sections relevant to the project. These are now in `FEEDS`:

- Straits Times — Singapore, Business
- Business Times — Singapore, Economy & Policy, Telcos / Media / Tech, Transport & Logistics, Startups / Tech, Technology

A fetch-only check on 2026-10-12 (no OpenAI calls) succeeded for all 11 RSS feeds:

```text
Fetched 237 → recent (24h) 39 → unique 35
Straits Times Singapore 18, Straits Times Business 8, Business Times Singapore 3,
BT Telcos/Media/Tech 2, BT Transport & Logistics 2, BT Startups & Tech 2
```

Observations:

- All 35 recent items came from Straits Times / Business Times; none came from a GeoAI source. With the old GeoAI RSS feeds commented out and the product score requiring AI × GeoAI × transport, the digest may be dominated by general Singapore news, or come out empty after thresholding.
- 35 unique URLs had only 33 unique titles: the same story appears under different URLs across ST/BT sections. URL-only deduplication misses these, which costs extra scoring calls and can duplicate digest entries.

### 2.5 Relevance thresholding — implemented

`MIN_TOTAL_SCORE = 20` has now been added to `config.py`, and `main.py` filters ranked articles before selecting the final digest items. The digest size is now configurable via `TOP_RANKED = 8` (was a hard-coded Top 5):

```python
qualified_articles = [
    article
    for article in ranked_articles
    if article.total_score >= MIN_TOTAL_SCORE
]

top_N = qualified_articles[:TOP_RANKED]
```

This means the digest no longer has to be padded with weakly relevant stories. If only three articles meet the threshold, only three are selected. Python list slicing is safe when fewer than `TOP_RANKED` items are available.

If no article qualifies, `generate_digest([])` still writes a digest containing only the header. Consider an explicit "no relevant articles today" message.

The initial threshold of 20 is a tuning parameter, not yet a final calibrated value; it should be reviewed over several daily runs.

### 2.6 Digest output preservation — implemented

`save_digest()` no longer overwrites the earlier digest when the pipeline runs more than once on the same day. Filenames follow this sequence:

```text
digest-2026-10-12.md
digest-2026-10-12(1).md
digest-2026-10-12(2).md
...
```

This is useful during source and scoring experiments because each run can be compared without losing the previous output.

`save_digest()` now writes to `<project root>/output` (resolved from the module's location) instead of a path relative to the current working directory. Previously, running from inside `src/` created a stray `src/output/` folder.

### 2.7 Freshness window shortened to 24 hours

`RECENT_HOURS` was reduced from 48 to 24. This suits daily news feeds (ST/BT) but makes weekly sources (Substacks) and search-derived results (Esri) even less likely to appear. A per-source lookback window, e.g. 7 days for weekly sources, is a candidate fix; it works best once SQLite (v0.3) prevents the same article resurfacing.

---

## 3. Key learnings so far

- **Source freshness remains the main quality constraint.** A technically valid source may still be too infrequent to contribute to a 24-hour digest.
- **RSS should remain the preferred ingestion method when available.** It is simpler and more deterministic than scraping or search.
- **Use search as a fallback, not the default.** Esri demonstrated the case where RSS and direct scraping are blocked, making search-based ingestion pragmatic.
- **Search may lag.** Search-based discovery depends on what the search service has discovered/indexed and may have incomplete publication metadata.
- **Scraping can work well for structured archives.** AI Daily Brief is a good example: direct access works and stable HTML selectors expose title, date, link, and teaser.
- **One common `Article` model remains valuable.** RSS, search, and scraping can all feed the same downstream filter → dedupe → score → rank → digest pipeline.
- **Timestamp normalization matters.** All `published_at` values should be stored internally as timezone-aware UTC datetimes.
- **Source-specific adapters are acceptable.** Keep source-specific complexity isolated (`esri_search.py`, `aidailybrief.py`) while preserving a common downstream pipeline.
- **Thresholding should happen after scoring/ranking and before Top-N selection.** `MIN_TOTAL_SCORE = 20` now prevents weak stories from being included just to fill the digest.

---

## 4. Next extensions (priority order)

### 1. Finish v0.2 source coverage and freshness

- [x] Add a working Esri fallback via search
- [x] Validate a robust Substack RSS retrieval pattern
- [x] Build an AI Daily Brief archive scraper
- [x] Add GeoAI Unpacked and Geospatial Law Substack feeds
- [x] Add Straits Times RSS sections (fetch OK 2026-10-12)
- [x] Add Business Times RSS sections (fetch OK 2026-10-12)
- [x] Basic per-source counts printed in `main.py` (RSS / Esri / AI Daily Brief / combined / recent)
- [ ] Switch `validate_feeds.py` to the `requests → feedparser` pattern (`load_feed()`)
- [ ] Decide whether to restore the original GeoAI RSS feeds (currently commented out in `config.py`)
- [ ] Decide on the `FEEDS2` experiment (Medium GeoAI works; Esri RSS returns 403): promote or remove
- [ ] Consider per-source lookback windows for weekly sources
- [ ] Continue searching for stronger land-transport / ITS sources
- [ ] Run the expanded source mix end-to-end and review digest quality

### 2. Relevance thresholding

- [x] Add `MIN_TOTAL_SCORE = 20` to `config.py`
- [x] Filter ranked articles in `main.py` before Top-N selection
- [x] Allow fewer than `TOP_RANKED` (now 8) items if only a few are genuinely relevant
- [ ] Tune the product-score threshold based on several daily runs

### 3. SQLite repository

- Store article metadata, scores, dates, source, and digest status
- Avoid rescoring articles already seen (saves API cost)
- Avoid resurfacing the same article across wider lookback windows
- Create the foundation for historical search

### 4. WhatsApp-friendly output

- Produce compact plain-text formatting
- Shorter summaries
- Easy copy/paste

### 5. Robustness

- Retry failed API calls (currently one failure can abort the whole run)
- Handle feed and source-adapter errors gracefully: wrap each feed in `fetch_articles()` and each adapter call in `main.py` in try/except, so one failing source doesn't stop the digest (**high priority** now that `load_feed()` raises on HTTP errors)
- Deduplicate on normalized title as well as URL (ST/BT cross-posts)
- Restrict Esri search results to `https://www.esri.com/arcgis-blog/` URLs (the domain filter allows all of `esri.com`, and URLs/dates come from the model unverified)
- Strip HTML from RSS summaries
- Create the OpenAI client lazily instead of at import time in `scoring.py` and `digest.py`
- Canonicalize URLs before deduplication, especially for search-derived results
- Decide how to handle articles with missing or uncertain publication dates

### 6. Testing and cleanup

- Add proper unit tests (e.g. pytest with hand-built `Article` objects for filtering, deduplication, ranking)
- Add source-adapter tests for RSS, Esri search, and AI Daily Brief scraping
- Remove scratch code when no longer needed: `openAI.py`, `substack.py`, `src/geoai_signal_feed.xml` (225 KB debug dump; don't commit), commented-out blocks in `feeds.py` / `main.py` / `aidailybrief.py`
- Remove unused imports in `feeds.py` (`random`, `fetch_esri_articles`)
- Remove `playwright` from `pyproject.toml` (`esri_browser.py` is gone; nothing imports it)
- Declare `pydantic` in `pyproject.toml` (used directly; only installed via `openai`)
- ~~Fix hard-coded "24 hours" message in `feeds.py`~~ — done (uses `RECENT_HOURS`)

---

## 5. Roadmap

```text
v0.1  MVP pipeline                      ✅ complete
v0.2  better sources + thresholding     🚧 in progress
v0.3  SQLite repository
v0.4  WhatsApp-ready digest
v0.5  searchable web interface
v0.6  embeddings / RAG
v0.7  agentic research
```

Robustness and testing/cleanup continue alongside each release rather than as separate versions.

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
├── docs/
│   └── sample-digest.md        # example output from the first v0.1 run
├── output/                     (generated digests; local only, git-ignored)
└── src/
    └── aimobility_news/
        ├── __init__.py
        ├── main.py             # pipeline entry point / orchestration
        ├── config.py           # feeds, freshness window, threshold, Top-N, model
        ├── models.py           # Article dataclass (+ score fields)
        ├── feeds.py            # RSS fetch (requests → feedparser), filter recent, deduplicate
        ├── scoring.py          # OpenAI relevance scoring
        ├── ranking.py          # sort by total_score
        ├── digest.py           # OpenAI summary + why-it-matters -> Markdown
        ├── esri_search.py      # Esri search-based source adapter
        ├── aidailybrief.py     # AI Daily Brief HTML source adapter
        ├── substack.py         # scratch: Substack/RSS test module
        ├── openAI.py           # scratch: list available models
        └── validate_feeds.py   # RSS feed health check (still uses feedparser.parse(url))
```

`esri_browser.py` (the Playwright experiment) has been deleted; only a stale `.pyc` remains in `__pycache__/`. `src/geoai_signal_feed.xml` is an untracked debug dump.

### Environment

- `uv` 0.12.24, Python 3.11.1 (`requires-python = ">=3.10"`)
- Corporate TLS: use the system certificate store:

```powershell
uv sync --system-certs
uv add <package> --system-certs
```

- Declared dependencies: `feedparser`, `openai`, `requests`, `beautifulsoup4`, plus `playwright` (left over from the Esri browser experiment and no longer used; remove it). `pydantic` is used directly but not declared.
- OpenAI credentials come from the `OPENAI_API_KEY` environment variable. `.env` / `.env.*` are git-ignored; no keys should be stored in the repository.
- Package modules using relative imports should normally be run with `-m`, e.g.:

```powershell
uv run python -m aimobility_news.main
```

### Configuration (`config.py`)

```python
FEEDS = { ... }          # 3 Substacks + 2 Straits Times + 6 Business Times sections
FEEDS2 = { ... }         # experiment: Medium GeoAI, Esri RSS (403); swap via `# FEEDS = FEEDS2`
RECENT_HOURS = 24
MIN_TOTAL_SCORE = 20
SCORING_MODEL = "gpt-6.1-sol"   # also used by esri_search.py and digest.py
TOP_RANKED = 8
```

The six original v0.1 RSS feeds (GIM International, Geospatial World, OGC, QGIS Blog, Planet OSGeo, Smart Cities Dive) are currently commented out.

### Current pipeline

```text
RSS feeds ---------------------\
                               \
Esri search --------------------→ Article objects
                               /
AI Daily Brief scraper --------/

→ filter_recent_articles()     keep last RECENT_HOURS; undated articles dropped
→ deduplicate_articles()       currently by exact URL
→ score_articles()             OpenAI: AI / GeoAI / transport scores
→ rank_articles()              total_score descending
→ threshold                    keep only total_score >= MIN_TOTAL_SCORE
→ [:TOP_RANKED]                up to Top 8
→ generate_digest()            OpenAI summary + "why it matters"
→ save_digest()                Markdown file in output/
```

### Where LLM capabilities are currently used

```text
scoring.py
→ relevance judgement and structured 1–5 scores

digest.py
→ 2–3 sentence summary + "why it matters"

esri_search.py
→ web-search-assisted Esri discovery + structured search results
```

Everything else — RSS retrieval, scraping, filtering, deduplication, ranking, and file writing — is conventional deterministic code.

### Scoring

OpenAI structured output (`client.responses.parse` with Pydantic `ArticleScore`) on the title and source summary. Three criteria, each an integer 1–5:

- `ai_score` — artificial intelligence
- `geoai_score` — GIS, geospatial, spatial analytics, mapping, digital twins, GeoAI
- `transport_score` — land transport: roads, rail, buses, traffic, mobility, planning, operations

`total_score = ai_score × geoai_score × transport_score` (range 1–125).

The product deliberately rewards intersection across all three themes; e.g. 5×1×1 = 5 while 3×3×3 = 27.

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

**Timestamp convention:** normalize `published_at` to timezone-aware UTC wherever possible.

### Source status

Validate RSS sources with:

```powershell
uv run python -m aimobility_news.validate_feeds
```

| Source | Method | Status | Notes |
|---|---|---|---|
| GIM International | RSS | Commented out | Large feed, but often stale |
| Geospatial World | RSS | Commented out | Geo / GIS source |
| Open Geospatial Consortium | RSS | Commented out | Standards / geospatial |
| QGIS Blog | RSS | Commented out | Useful but infrequent |
| Planet OSGeo | RSS | Commented out | Non-fatal encoding warning observed |
| Smart Cities Dive | RSS | Commented out | Fresh but broad/noisy |
| GeoAI Signal | RSS via requests → feedparser | Active | 9 entries in test; strong but roughly weekly |
| GeoAI Unpacked | RSS via requests → feedparser | Active | Fetch OK 2026-10-12; GeoAI source |
| Geospatial Law | RSS via requests → feedparser | Active | Fetch OK 2026-10-12; governance / policy |
| Straits Times (Singapore, Business) | RSS | Active | Fetch OK 2026-10-12; 26 of 35 recent items |
| Business Times (6 sections) | RSS | Active | Fetch OK 2026-10-12; overlaps with ST (same story, different URLs) |
| Esri ArcGIS Blog | OpenAI web search | Active | RSS 403 (re-checked 2026-10-12); requests / Playwright blocked |
| AI Daily Brief | HTML scrape | Active | Fresh general-AI source; one edition = one Article; date-only (00:00 UTC) |
| Medium — GeoAI | RSS | In `FEEDS2` (inactive) | HTTP 200 on 2026-10-12; candidate to promote |
| ITS International | RSS | Failed | 404; revisit via alternate ingestion if worthwhile |
| Sustainable Bus - ITS | RSS | Failed | 0 entries / parse issue |
| Railway Gazette - Metro | RSS | Failed | 404 |

A valuable source does not necessarily have a usable RSS feed; source-specific adapters are now an accepted part of the architecture.

### Commit history carried forward from v0.1

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

Add the new v0.2 commits here after committing today's source-ingestion work.

---

## Resume point

MVP v0.1 remains complete. MVP v0.2 has made substantial progress on **source coverage and ingestion diversity**, but none of the v0.2 work is committed yet:

- Esri search fallback works
- RSS retrieval in `feeds.py` uses `requests → feedparser`
- AI Daily Brief scraping is implemented with the correct title/summary selectors
- Three Substacks, two Straits Times sections and six Business Times sections are in `FEEDS` and fetch successfully
- `MIN_TOTAL_SCORE = 20` thresholding and configurable `TOP_RANKED = 8` are in place
- `save_digest()` no longer overwrites same-day digests
- `RECENT_HOURS` is now 24

Next:

1. **Make source failures non-fatal** (try/except per feed and per adapter). This is the main blocker for reliable daily runs.
2. Switch `validate_feeds.py` to `load_feed()`; add title-based deduplication.
3. Clean up before committing: remove `playwright`, add `pydantic`, delete `substack.py` / `geoai_signal_feed.xml` / unused imports, and resolve `FEEDS2`.
4. Commit the v0.2 source-ingestion work.
5. Run the expanded source mix end-to-end over several days, check the GeoAI vs. general-news balance, and tune `MIN_TOTAL_SCORE`.

Once that is stable, v0.2 should be ready to close.

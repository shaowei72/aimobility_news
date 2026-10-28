# AI Mobility News App — Checkpoint

_Last updated: 2026-10-28 — MVP v0.2 in progress_

## Project

`aimobility-news`  
Python package: `aimobility_news`  
Local folder: `E:\MyLocalDev\AIMobility\aimobility_news`  
Remote: https://github.com/shaowei72/aimobility_news

**Goal:** a daily AI-powered news intelligence digest on **AI applied to land transport**, with emphasis on GeoAI and the use of GIS in transport, for transport authorities, operators, planners, and geospatial teams.

The focus narrowed on 2026-10-28 from three themes (AI × GeoAI × land transport) to two scored domains, AI and land transport, with GeoAI and GIS rewarded at the top of each scale instead of being a separate requirement. The digest title is now "AI × Transport".

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

First successful end-to-end run: 2026-10-10. Released in commit `8a47bfa`.

---

## 2. MVP v0.2 — progress

v0.2 covers **source coverage and freshness**, **relevance thresholding**, and, since 2026-10-28, **a new scoring method** and **full-text scoring**.

### 2.1 Source adapters (committed in `02807a8`)

- **Esri ArcGIS Blog via OpenAI web search** (`esri_search.py`). RSS returns 403, and `requests` / Playwright are blocked. Dates are normalised to timezone-aware UTC.
- **AI Daily Brief archive scraper** (`aidailybrief.py`), using `a.ed-title` links and the `.ed-main .ed-teaser` summary. One edition = one `Article`.
- **RSS via `requests → feedparser.parse(response.content)`** instead of `feedparser.parse(url)`, which failed on some Substack feeds.

### 2.2 Relevance thresholding and output (committed in `02807a8`)

- `MIN_TOTAL_SCORE` filters ranked articles before Top-N selection; `TOP_RANKED` sets the maximum digest size (8). Fewer items are allowed when few are relevant.
- `save_digest()` never overwrites same-day digests (`digest-YYYY-MM-DD(1).md`, …) and always writes to `<project>/output`.

### 2.3 New scoring method: AI × transport (committed in `6581a8e`)

The original score was `ai × geoai × transport`, each 1–5. In practice it was too harsh: a 1 meant "not or weakly relevant" but still multiplied as a neutral value, single-theme stories (5×1×1) scored the same as unrelated ones, and general news clustered at 1–8 so digests came out empty. A pairwise-sum variant was tried briefly.

The current method uses two criteria, each an integer **0–5** (0 = not relevant), and each with a one-sentence reason (`ai_reason`, `transport_reason`) generated before the score:

| Level | `ai_score` | `transport_score` |
|---|---|---|
| 0 | No AI content | No land transport content |
| 1 | Passing mention / buzzword | Passing mention |
| 2 | General AI news (models, funding, regulation) | Routine transport news (accidents, fares, earnings) |
| 3 | Concrete AI application, non-spatial | Substantive planning / operations / policy, non-spatial |
| 4 | AI on spatial or location data is significant | Spatial / location data is significant to the story |
| 5 | GeoAI is the central subject | GIS / geospatial for transport is the central subject |

`total_score = ai_score × transport_score` (range 0–25). An article must touch both domains to score above 0, and spatial content raises both axes, so GeoAI-for-transport stories (16–25) rank clearly above non-spatial AI-in-transport (~9).

The prompt also includes general rules (score only what the text says; pick the lower level when between two; marketing language does not raise a score above 1; when full text is given, score its main subject) and borderline guidance for autonomous vehicles, EVs, ride-hailing, freight, aviation/maritime, smart cities, property, disasters, digital twins, newsletters, and "algorithms/analytics" wording. See `scoring.py`.

Land transport only: aviation and maritime score 0 unless the article concerns their land-side connections.

**Threshold guidance:** `MIN_TOTAL_SCORE = 9` means both criteria at least "clearly relevant" (3×3); 12 effectively requires a spatial element on one axis. The committed value is currently **3**, a test setting.

### 2.4 Full-text scoring (committed in `6581a8e`)

RSS summaries are often one sentence (Straits Times / Business Times ~15 words, Substack subtitles ~13 words), so scoring on them was conservative and digest summaries lacked detail. Now:

- `Article.content` holds the full article text (plain text) when available.
- `extract_content()` takes the longest of `entry.content` and the summary, and treats it as full text only if it has at least `FULL_TEXT_MIN_WORDS` (150) words. This covers feeds that put the article in `<content:encoded>` (Substack, OGC, NVIDIA, MIT) and feeds that put it in `<description>` (IEEE Spectrum, Berkeley AI Research), and ignores short teasers or image-only bodies.
- For sources in `PAGE_FETCH_SOURCES` (Google Research, Google DeepMind, Hugging Face Blog), whose feeds carry 0–13 words, the article webpage is fetched with `requests` and extracted with `trafilatura`. This runs **after** the recency filter and deduplication, so only recent articles are fetched (about 0.4 s per page).
- Scoring and digest generation both use `text_for_scoring()`: full text capped at `MAX_CONTENT_WORDS` (1,500), otherwise the summary. The prompt labels which one it is.
- Summaries are stripped of HTML. Feed entries without a title or link are skipped.

Full-text availability checked on 2026-10-28:

| Source | Where the full text is | Typical length |
|---|---|---|
| GeoAI Signal, GeoAI Unpacked, Geospatial Law | `entry.content` | 640–1,900 words |
| Open Geospatial Consortium | `entry.content` | ~610 words |
| MIT Autonomous Vehicles, NVIDIA Blog | `entry.content` | 830–1,100 words |
| IEEE Spectrum, Berkeley AI Research | summary (`<description>`) | 670–3,800 words |
| Google Research, Google DeepMind, Hugging Face | webpage (`trafilatura`) | 900–4,000 words |
| Planet OSGeo | summary, mixed | 9–2,250 words |
| QGIS Blog | summary extracts | ~90 words |
| GIM International, Smart Cities Dive, Straits Times, Business Times | summary only | 12–30 words |

### 2.5 Robustness and tooling (committed in `6581a8e`)

- One failing feed no longer aborts the run: `fetch_articles()` catches `requests.RequestException` per feed and prints a warning.
- `validate_feeds.py` fetches with `requests` and reports HTTP status, content type, and parse errors.
- AI Daily Brief editions are stamped at **23:59:59 UTC** on their date. Previously they were stamped 00:00 UTC, which made each edition look up to a day older, so none passed a 24-hour filter for most of the day. Side effect: evening (SGT) runs may include the same edition on two consecutive days.
- `main.py` times each pipeline step and prints a summary sorted slowest first.
- `feeds.py` has two debugging helpers: `inspect_feed_structure()` and `inspect_article_webpage()`.

### 2.6 Active feed set

`config.py` defines several feed sets; `FEEDS = FEEDS_NEW` is active:

- **`FEEDS_NEW` (active):** MIT Autonomous Vehicles, The Robot Report (**403, skipped**), NVIDIA Blog, Google Research, Google DeepMind, Berkeley AI Research, Hugging Face Blog
- **Specialist set (defined as `FEEDS`, then overridden):** IEEE Spectrum Full Text, IEEE Spectrum Robotics, OGC, GeoAI Signal, GeoAI Unpacked, Geospatial Law; ITS International commented out (unconfirmed endpoint)
- **Commented out:** GIM International, Geospatial World, OGC, QGIS Blog, Planet OSGeo, Smart Cities Dive, Straits Times (2 sections), Business Times (6 sections)
- **`FEEDS2` (experiment):** Medium GeoAI, Esri RSS (403)

Esri search and AI Daily Brief run on every pipeline run, independent of `FEEDS`.

Content fit: the `FEEDS_NEW` sources are mostly general AI / ML research. Under the AI × transport rubric most of their articles will score transport 0 and fall below the threshold, so they add scoring cost more often than digest items. Review this against logged scores.

---

## 3. Key learnings

- **Source freshness is the main quality constraint.** A valid source may publish too rarely to contribute to a 24-hour digest.
- **RSS is preferred when available**; use search as a fallback (Esri) and scraping for structured archives (AI Daily Brief).
- **Search-based discovery may lag** and returns model-written URLs, dates and summaries that are not verified.
- **One common `Article` model** lets RSS, search, scraping and page fetching feed the same downstream pipeline.
- **Normalise timestamps** to timezone-aware UTC. For date-only sources, stamping at the start of the day silently drops them from short windows.
- **Feeds put full text in different places** (`content:encoded`, `description`, or nowhere). Check where before assuming a feed is summary-only.
- **Fetch webpages only after filtering.** Some feeds list hundreds of entries (Hugging Face: 891).
- **Multiplicative scores need a true zero.** A 1–5 scale where 1 means "not relevant" distorts products; 0–5 with 0 = none makes `ai × transport` behave cleanly.
- **Threshold after scoring/ranking, before Top-N**, and expect to retune it whenever the formula or rubric changes.

---

## 4. Next steps (priority order)

### 1. Settle production settings and source mix

- [ ] Set `MIN_TOTAL_SCORE` (recommended 9) and `RECENT_HOURS` (24) back from test values (3 and 72)
- [ ] Decide the active feed set: `FEEDS_NEW` (general AI / robotics) vs the specialist / GeoAI / Singapore sets; consider merging
- [ ] Remove or replace The Robot Report (403 with the current User-Agent)
- [ ] Fix the QGIS URL if re-enabled: `https://blog.qgis.org/index.xml` (`/feed` returns 404)
- [ ] Continue searching for AI-in-transport / ITS sources
- [ ] Consider per-source lookback windows for weekly sources

### 2. Calibrate scoring

- [ ] Log every article's scores and reasons (JSON or CSV) per run, so the threshold and rubric can be tuned without extra API calls
- [ ] Run several days and review digest quality and score distribution
- [ ] Write a "no relevant articles today" message when nothing qualifies (the digest is currently header-only)

### 3. SQLite repository (v0.3)

- Store article metadata, text, scores, reasons, dates, source, and digest status
- Avoid rescoring and refetching articles already seen
- Avoid resurfacing the same article across wider lookback windows (e.g. AI Daily Brief on consecutive evenings)

### 4. WhatsApp-friendly output (v0.4)

- Compact plain-text formatting, shorter summaries, easy copy/paste

### 5. Robustness (from the 2026-10-28 code review)

- Esri search: restrict to `https://www.esri.com/arcgis-blog/` URLs; its summary is model-written with a GeoAI framing, which may inflate `ai_score`; it asks for 7 days but the window is shorter, so most results are discarded after a paid call
- `validate_feeds.py`: reuse `load_feed()` (it currently uses a different timeout and headers); also report dated entries, recent entries, and full-text availability
- Deduplicate on normalised title and canonical URL (strip `utm_*`), not only exact URL
- Strip `script`, `style` and `figcaption` in `html_to_text()`; image credits and share/subscribe footers currently get through
- `inspect_article_webpage()`: fetch with `requests`, handle unknown source names
- Warn when AI Daily Brief returns no editions (HTML change)
- Retry failed API calls; wrap Esri and AI Daily Brief calls in `main.py` so an adapter failure does not abort the run
- Create the OpenAI client lazily instead of at import time in `scoring.py` and `digest.py`

### 6. Testing and cleanup

- Add pytest tests with hand-built `Article` objects (filtering, dedupe, ranking, `extract_content()`, `text_for_scoring()`)
- Remove scratch code: `openAI.py`, `substack.py`, `src/geoai_signal_feed.xml` (225 KB debug dump, tracked in git), commented-out blocks
- Remove unused imports in `feeds.py` (`random`, `fetch_esri_articles`)
- Remove `playwright` from `pyproject.toml` (unused); declare `pydantic` (used directly)
- Regenerate `docs/sample-digest.md` with the new scoring (current sample is from v0.1)

---

## 5. Roadmap

```text
v0.1  MVP pipeline                      ✅ complete
v0.2  sources, scoring, full text       🚧 in progress
v0.3  SQLite repository
v0.4  WhatsApp-ready digest
v0.5  searchable web interface
v0.6  embeddings / RAG
v0.7  agentic research
```

Robustness and testing/cleanup continue alongside each release rather than as separate versions.

---

## Reference

### Current pipeline

```text
RSS feeds (FEEDS) ------------\
Esri search -------------------→ Article objects
AI Daily Brief scraper -------/

→ filter_recent_articles()     keep last RECENT_HOURS; undated articles dropped
→ deduplicate_articles()       exact URL
→ add_page_content()           webpage full text for PAGE_FETCH_SOURCES
→ score_articles()             OpenAI: ai_score, transport_score (0–5) + reasons
→ rank_articles()              total_score = ai × transport, descending
→ threshold                    total_score >= MIN_TOTAL_SCORE
→ [:TOP_RANKED]                up to Top 8
→ generate_digest()            OpenAI summary + "why it matters" (same capped text)
→ save_digest()                Markdown file in output/
→ timing summary
```

### Where LLM capabilities are used

```text
scoring.py      relevance scores + reasons (structured output)
digest.py       2–3 sentence summary + "why it matters"
esri_search.py  web-search-assisted Esri discovery
```

Everything else (RSS retrieval, scraping, page extraction, filtering, deduplication, ranking, file writing) is deterministic code.

### Configuration (`config.py`)

```python
FEEDS = FEEDS_NEW            # see section 2.6
RECENT_HOURS = 72            # test value; 24 for daily use
MIN_TOTAL_SCORE = 3          # test value; 9 recommended
SCORING_MODEL = "gpt-6.1-sol"
MAX_CONTENT_WORDS = 1500
FULL_TEXT_MIN_WORDS = 150
PAGE_FETCH_SOURCES = {"Google Research", "Google DeepMind", "Hugging Face Blog"}
TOP_RANKED = 8
```

### Article model (`models.py`)

```python
@dataclass
class Article:
    title: str
    url: str
    source: str
    published_at: datetime | None
    summary: str | None
    content: str | None = None      # full article text, when available

    ai_score: int | None = None
    ai_reason: str | None = None
    transport_score: int | None = None
    transport_reason: str | None = None
    total_score: int | None = None
```

### Environment

- `uv`, Python 3.11 (`requires-python = ">=3.10"`)
- Corporate TLS: `uv sync --system-certs`, `uv add <package> --system-certs`
- Dependencies: `feedparser`, `openai`, `requests`, `beautifulsoup4`, `trafilatura`, plus unused `playwright`; `pydantic` is used but not declared
- `OPENAI_API_KEY` from the environment; `.env` files are git-ignored
- Run modules with `-m`, e.g. `uv run python -m aimobility_news.main`

### Commit history

```text
6581a8e Score on AI x transport with full article text; add timing and new feeds
02807a8 Add v0.2 source adapters, relevance threshold, and fixed output path
ada1962 Update checkpoint for MVP v0.1 completion and add roadmap
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

All work up to 2026-10-28 is committed and pushed. The pipeline scores on AI × transport (0–5 each) using full article text where available, including webpage fetching for Google Research, Google DeepMind and Hugging Face.

Next:

1. Restore production settings (`MIN_TOTAL_SCORE = 9`, `RECENT_HOURS = 24`) and decide the active feed set.
2. Log per-article scores and reasons, run for several days, and tune the threshold.
3. Add the "no relevant articles today" message.
4. Work through the robustness and cleanup items, then close v0.2 and start the SQLite repository (v0.3).

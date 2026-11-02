# AI Mobility News App — Checkpoint

_Last updated: 2026-11-02 — v0.2 in progress, v0.3 (local LLM via Ollama) next_

## Project

`aimobility-news`  
Python package: `aimobility_news`  
Local folder: `E:\MyLocalDev\AIMobility\aimobility_news`  
Remote: https://github.com/shaowei72/aimobility_news

**Objective:** a personal AI-powered news intelligence system on **AI × land transport**, with particular interest in GeoAI, GIS, intelligent transport systems, and Singapore's transport landscape. It starts as an automated daily digest and is meant to grow into a locally powered, searchable news intelligence and research assistant.

The digest title is "GIS × AI × Transport". Articles are scored on three independent domains (transport, AI, GIS/GeoAI), combined so that transport plus AI and/or GIS ranks highest (section 2.3).

---

## Roadmap (revised 2026-11-02)

| Version | Focus | Status |
|---|---|---|
| **v0.1** | End-to-end MVP news pipeline | ✅ Complete |
| **v0.2** | Source coverage, full-text extraction and relevance scoring | 🚧 In progress |
| **v0.3** | Local LLM integration using Ollama | Next |
| **v0.4** | SQLite news repository | Planned |
| **v0.5** | WhatsApp-ready digest | Planned |
| **v0.6** | Searchable web interface | Planned |
| **v0.7** | Embeddings, semantic search and RAG | Planned |
| **v0.8** | Agentic news research | Planned |

Changes from the previous roadmap: local LLM inference via Ollama is inserted as v0.3, and every later version moves down one number. Automatic WhatsApp delivery remains out of scope.

### Engineering principles (all releases)

- **Modularity:** separate ingestion, extraction, scoring, summarisation, persistence and presentation.
- **Model independence:** no application logic tightly coupled to one LLM.
- **Source traceability:** keep links to original sources; distinguish reported facts from generated interpretation.
- **Incremental delivery:** each version is independently usable.
- **Testing and observability:** tests, diagnostics, error handling and timing added progressively.
- **Local-first where practical:** prefer local inference and storage; keep cloud services where they add real value (e.g. web search).

### Immediate priorities

1. Complete v0.2 source ingestion and full-text extraction, particularly AI Daily Brief.
2. Stabilise the transport × AI × GIS scoring and daily digest quality.
3. Build a small, representative evaluation dataset **before** moving to local inference.
4. Start v0.3 with the LLM provider abstraction and Ollama model benchmarks.

---

## 1. v0.1 — MVP pipeline (complete)

RSS ingestion, recent-article filtering, deduplication, OpenAI relevance scoring, ranking and Top 5, AI-generated summary + "why it matters", Markdown digest output.

First successful end-to-end run: 2026-10-10. Released in commit `8a47bfa`.

**Exit criterion:** a working end-to-end pipeline producing a daily digest. ✅

---

## 2. v0.2 — Better sources, extraction and scoring (in progress)

**Objective:** improve the relevance, freshness, completeness and quality of coverage.

**Exit criterion:** a reliable daily digest with relevant articles supported by sufficiently rich source content.

### 2.1 Source adapters (`02807a8`)

- **Esri ArcGIS Blog via OpenAI web search** (`esri_search.py`). RSS returns 403, and `requests` / Playwright are blocked. Dates normalised to timezone-aware UTC.
- **AI Daily Brief archive scraper** (`aidailybrief.py`): `a.ed-title` links and `.ed-main .ed-teaser` summary; one edition = one `Article`. Editions are stamped 23:59:59 UTC on their date so they pass a 24-hour filter.
- **RSS via `requests → feedparser.parse(response.content)`**, which fixed some Substack feeds.

**In progress:** `aidailybrief_transcript.py` checks that each edition is also published as Markdown, at `<edition_url>.md` (digest) and `<edition_url>/transcript.md` (podcast transcript). Next step: use these as the edition's full text, and possibly split an edition into individual news items.

### 2.2 Feed set (`config.py`)

`FEEDS` merges three groups:

- **`FEEDS_transport`:** MIT Autonomous Vehicles, InsideEVs Autonomous Vehicles, ADAS & Autonomous Vehicle International, The Robot Report (**403**), IEEE Spectrum Robotics, TransportXtra Technology, TransportXtra Passenger Technology, Smart Cities Dive, Tech Xplore Automotive, Railway-News, Railway Age. Commented out to test: TechCrunch Transportation, The Verge Transportation, Electrek, Transport Topics, ITS International (403).
- **`FEEDS_AI`:** IEEE Spectrum Full Text, NVIDIA Blog, Google Research, Google DeepMind, Berkeley AI Research, Hugging Face Blog, Tech Xplore Robotics, Tech Xplore AI, NVIDIA Developer Robotics, InsideEVs Artificial Intelligence.
- **`FEEDS_gis`:** Open Geospatial Consortium, GeoAI Signal, GeoAI Unpacked, Geospatial Law. Geospatial World commented out.

Esri search and AI Daily Brief run on every pipeline run, independent of `FEEDS`.

Many transport sources (TransportXtra, Railway Age, Railway-News, Smart Cities Dive, InsideEVs, Tech Xplore) appear to be summary-only, so scoring and summaries for them rely on 12–30-word teasers. To verify per source; see 2.5.

### 2.3 Scoring: transport, AI and GIS (`b73b3a0`)

Each article gets three independent integer scores 0–5, each with a one-sentence reason generated before the score (`transport_*`, `ai_*`, `gis_*`). All three use the same level meanings, scored on relevance **and** significance:

| Level | Meaning |
|---|---|
| 0 | No meaningful content in the domain |
| 1 | Incidental mention or marketing buzzword |
| 2 | Routine or general news |
| 3 | Substantive development or concrete application |
| 4 | Significant advance, innovation or deployment |
| 5 | Highly consequential development or breakthrough |

- **Transport:** land transport (roads, rail/MRT/LRT, buses, taxis and ride-hailing, AVs, micromobility, land freight, planning, policy, safety), with particular interest in Singapore and ITS. Aviation and maritime only for land-side connections.
- **AI:** AI technology, research, applications, deployment and governance.
- **GIS:** GIS platforms, geospatial data and standards, imagery and remote sensing, LiDAR, GNSS, location intelligence, digital twins, GeoAI.

Combined score (`combine_scores()` in `scoring.py`):

```text
total_score = (transport + 1) × (ai + gis + 1) − 1        # 0–65
            = transport + ai + gis + transport × (ai + gis)
```

| Transport / AI / GIS | Total |
|---|---|
| 5 / 5 / 5 | 65 |
| 4 / 4 / 0 | 24 |
| 3 / 3 / 0 | 15 |
| 2 / 3 / 0 | 11 |
| 0 / 5 / 5 | 10 |
| 0 / 5 / 0 | 5 |

A single domain scores at most 5, AI + GIS without transport at most 10; transport combined with AI and/or GIS multiplies.

History: v0.1 used `ai × geoai × transport` (1–5 each), which was too harsh. On 2026-10-28 this became `ai × transport` (0–5 each, GeoAI rewarded at levels 4–5 of each axis, range 0–25). On 2026-11-02 GIS became a separate axis with the formula above, and levels 4–5 now mean significance rather than spatial content.

The revised roadmap text still describes "two-dimensional AI × transport scoring"; the code uses the three-domain method above.

### 2.4 Classification and digest selection

After scoring and ranking, `classify_articles()` (`ranking.py`) gives each article one label:

```text
total_score ≥ MIN_TOTAL_SCORE                   → qualified
else transport, AI or GIS ≥ its NOTABLE_MIN_*   → notable
else                                            → below threshold
```

`select_for_digest()` publishes qualified then notable articles, highest total first, up to `TOP_RANKED` (8). Notable articles always score below `MIN_TOTAL_SCORE`, so qualified ones always come first. Fewer than 8 items are published when fewer are relevant.

- **Digest** (`output/digest-YYYY-MM-DD.md`): qualified articles, then notable ones under "Also notable (strong in one domain)". Each shows `Score: 15 (Transport 3, AI 3, GIS 0)`, a summary and "why it matters". On an empty day: "No relevant articles today."
- **Debug digest** (`output/debug-digest-YYYY-MM-DD.md`): every scored article, highest total first, with status (`qualified, published`, `notable, over max`, `below threshold`, …), the three scores, the text it was scored on, and all three reasons. No LLM calls.

`Article` carries `digest_status` and `published` for this; both will map onto the v0.4 repository's digest-status column.

### 2.5 Full-text scoring (`6581a8e`)

- `Article.content` holds full plain text when available. `extract_content()` uses the longest of `entry.content` and the summary if it has ≥ `FULL_TEXT_MIN_WORDS` (150) words.
- For `PAGE_FETCH_SOURCES` (Google Research, Google DeepMind, Hugging Face Blog) the webpage is fetched with `requests` + `trafilatura`, **after** recency filtering and deduplication.
- Scoring and digest generation use `text_for_scoring()`: full text capped at `MAX_CONTENT_WORDS` (1,500), otherwise the summary.

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

The transport and AI feeds added since then have not been checked yet.

### 2.6 Robustness and tooling

- One failing feed no longer aborts the run (per-feed `requests.RequestException` handling).
- `validate_feeds.py` reports HTTP status, content type and parse errors.
- `main.py` times each step and prints a summary, slowest first.
- `feeds.py` debugging helpers: `inspect_feed_structure()`, `inspect_article_webpage()`.

### 2.7 Remaining v0.2 work

**Sources and extraction**
- [ ] AI Daily Brief: use the `.md` digest / `transcript.md` as full text; consider splitting editions into individual stories
- [ ] Separate source discovery from article extraction
- [ ] Check full-text availability for the new transport and AI feeds; add summary-only sources to `PAGE_FETCH_SOURCES` where pages extract cleanly
- [ ] Summarise published articles from the full webpage text instead of the RSS teaser (fetch only for the ≤ 8 published items; larger word cap for the digest than for scoring)
- [ ] Remove or replace The Robot Report (403)
- [ ] Continue searching for AI-in-transport / ITS / Singapore sources; consider per-source lookback windows for weekly sources

**Scoring and digest quality**
- [ ] Run several days and tune `MIN_TOTAL_SCORE` and `NOTABLE_MIN_*` from the debug digests. Current values are 11 and 3 / 3 / 3; `RECENT_HOURS = 72` is a test value (24 for daily use)
- [ ] Build the evaluation dataset (see 3.4); it is needed before v0.3 benchmarking

**Reliability**
- [ ] Deduplicate on normalised title and canonical URL (strip `utm_*`), not only exact URL
- [ ] Wrap Esri and AI Daily Brief calls in `main.py` so an adapter failure does not abort the run; warn when AI Daily Brief returns no editions
- [ ] Esri search: restrict to `https://www.esri.com/arcgis-blog/` URLs; its model-written summary may inflate scores; it requests 7 days but most results are then filtered out
- [ ] Strip `script`, `style` and `figcaption` in `html_to_text()`
- [ ] Retry failed API calls
- [ ] `validate_feeds.py`: reuse `load_feed()`; report dated, recent and full-text entries
- [ ] Add pytest tests with hand-built `Article` objects (filtering, dedupe, `combine_scores()`, classification, `extract_content()`, `text_for_scoring()`)

**Cleanup**
- [ ] Remove scratch code: `openAI.py`, `substack.py`, `src/geoai_signal_feed.xml` (225 KB, tracked), commented-out blocks
- [ ] Remove unused imports in `feeds.py` (`random`, `fetch_esri_articles`)
- [ ] Remove `playwright` from `pyproject.toml`; declare `pydantic`
- [ ] Regenerate `docs/sample-digest.md` (current sample is from v0.1)

---

## 3. v0.3 — Local LLM integration with Ollama (next)

**Objective:** run the core LLM functions locally, reducing reliance on paid cloud inference.

**Exit criterion:** end-to-end digest generation using a local Ollama model for scoring and summarisation, with results comparable to the OpenAI-based pipeline.

### 3.1 Environment (checked 2026-11-02)

| Item | Value |
|---|---|
| Ollama | 0.40.13, installed |
| Models pulled | `qwen3.5:9b` (6.6 GB), `qwen3:8b` (5.2 GB), `qwen3:4b` (2.6 GB) |
| GPU | NVIDIA RTX 5060 Ti, 16 GB VRAM |
| CPU / RAM | Intel i5-11400F, 64 GB |

8–9B models fit with room for a large context window; ~14B models fit at 4-bit quantisation.

### 3.2 Where the LLM is used today

| File | Use | Local? |
|---|---|---|
| `scoring.py` | transport / AI / GIS scores + reasons, one call per article | ✅ Migrate |
| `digest.py` | summary + "why it matters", one call per published article (≤ 8) | ✅ Migrate |
| `esri_search.py` | Esri discovery via OpenAI **web search** | ❌ Stays on OpenAI (a local model cannot search the web), or disabled in local-only mode |
| `openAI.py` | scratch | Remove |

All calls use `client.responses.parse(..., text_format=<Pydantic model>)`, and `OpenAI()` is created at import time in `scoring.py` and `digest.py`.

### 3.3 Plan

1. **Provider abstraction:** a small `llm.py` exposing roughly `parse(prompt, schema, model) -> schema instance`, with OpenAI and Ollama implementations. Scoring and digest call it instead of owning a client (also fixes import-time client creation). Config:
   ```python
   LLM_PROVIDER = "ollama"        # or "openai"
   SCORING_MODEL = "qwen3.5:9b"
   DIGEST_MODEL = "qwen3.5:9b"
   OLLAMA_NUM_CTX = 16384
   ```
   Ollama can be called through its OpenAI-compatible endpoint (`base_url="http://localhost:11434/v1"`) or its native API with the Pydantic JSON schema passed as `format`. Test both; the native API is usually the more reliable for structured output.
2. **Context window:** the scoring prompt is ~2,500 tokens of rubric plus up to 1,500 words of article (~5–6k tokens in total). If Ollama's context is smaller, it truncates the input silently and the scores look plausible but are wrong. Set `num_ctx` explicitly (8k–16k) and log prompt token counts.
3. **Reliable structured output:** temperature 0; constrain scores to 0–5 in the schema; retry or record a failure on invalid JSON; test Qwen thinking mode on vs off (slower, possibly more consistent on a long rubric).
4. **Evaluation dataset:** 30–50 representative articles (strong overlaps, single-domain, borderline around the threshold, summary-only), with full text saved so runs are repeatable without refetching. Hand labels where possible; at minimum, OpenAI scores as the reference.
5. **Benchmark:** for each model (`qwen3.5:9b`, `qwen3:8b`, one ~14B) compare against OpenAI:
   - share of domain scores differing by more than 1
   - agreement on qualified / notable / below threshold
   - overlap of the published Top 8
   - JSON validation failure rate
   - seconds per article, VRAM use
   - summary quality (manual review of a sample)
6. **Fallback:** keep OpenAI selectable per task, e.g. local scoring with OpenAI summaries, or the reverse.
7. **Optional:** extract individual stories from AI Daily Brief transcripts with the local model.

### 3.4 Expected trade-offs

- **Cost:** no per-call cost, which makes scoring the full feed set and fetching more full text affordable.
- **Speed:** a few seconds per article on the 5060 Ti; a few minutes per daily run is acceptable for a batch job.
- **Quality:** 8–9B models usually follow a long, nuanced rubric less consistently than frontier models; expect more variance near the threshold. The benchmark measures how much.
- **Privacy:** article text stays on the machine.

---

## 4. Later versions

### v0.4 — SQLite news repository
Store article metadata, dates, sources, extracted content, summaries, scores, reasons, **LLM model identifiers**, and digest status (`digest_status`, `published`). Avoid refetching and rescoring; track earlier digest appearances (e.g. AI Daily Brief on consecutive evenings); basic historical queries.

### v0.5 — WhatsApp-ready digest
Compact plain text with headlines, short summaries and links; configurable length; manual copy/paste. Automatic delivery out of scope.

### v0.6 — Searchable web interface
View current and past digests; search and filter by date, source and relevance; view summaries and scoring reasons; basic controls for configuration and digest generation. Backed by SQLite.

### v0.7 — Embeddings, semantic search and RAG
Embed articles; vector retrieval; natural-language questions over history; grounded answers with citations. Evaluate local embedding models (Ollama serves these) before cloud options.

### v0.8 — Agentic news research
Identify emerging themes, run targeted follow-up searches, compare sources, track developments over time, produce thematic briefings for configurable topics.

### Not yet on the roadmap (suggested)
- Scheduled daily runs (Windows Task Scheduler or similar)
- Token and cost tracking per run (relevant for comparing OpenAI with Ollama)

---

## 5. Key learnings

- **Source freshness is the main quality constraint.** A valid source may publish too rarely for a 24-hour digest.
- **RSS is preferred**; use search as a fallback (Esri) and scraping for structured archives (AI Daily Brief).
- **Search-based discovery may lag** and returns model-written URLs, dates and summaries that are not verified.
- **One common `Article` model** lets RSS, search, scraping and page fetching share the downstream pipeline.
- **Normalise timestamps** to timezone-aware UTC; for date-only sources, start-of-day stamps silently drop items from short windows.
- **Feeds put full text in different places** (`content:encoded`, `description`, or nowhere). Check before assuming a feed is summary-only.
- **Fetch webpages only after filtering** (Hugging Face lists 891 entries).
- **Multiplicative scores need a true zero**: 0–5 with 0 = none.
- **Score domains independently, combine in code.** Keeping the prompt about per-domain relevance and putting the weighting in `combine_scores()` makes the rubric easier to reason about and the formula easy to change without rescoring.
- **Label each article independently.** A fixed qualified / notable / below-threshold rule is simpler and easier to debug than slot-filling that depends on how many other articles qualified.
- **Retune thresholds whenever the formula or rubric changes.**

---

## Reference

### Current pipeline

```text
RSS feeds (FEEDS) ------------\
Esri search -------------------→ Article objects
AI Daily Brief scraper -------/

→ filter_recent_articles()     last RECENT_HOURS; undated articles dropped
→ deduplicate_articles()       exact URL
→ add_page_content()           webpage full text for PAGE_FETCH_SOURCES
→ score_articles()             OpenAI: transport, AI, GIS (0–5) + reasons
                               total = (T + 1) × (A + G + 1) − 1
→ rank_articles()              total_score, descending
→ classify_articles()          qualified / notable / below threshold
→ select_for_digest()          qualified then notable, up to TOP_RANKED
→ generate_digest()            OpenAI summary + "why it matters" per published article
→ generate_debug_digest()      all scored articles, scores and reasons (no LLM)
→ save_digest()                output/digest-*.md, output/debug-digest-*.md
→ timing summary
```

### Configuration (`config.py`)

```python
FEEDS = {**FEEDS_transport, **FEEDS_AI, **FEEDS_gis}
RECENT_HOURS = 72                  # test value; 24 for daily use
MIN_TOTAL_SCORE = 11               # on the 0–65 scale
NOTABLE_MIN_TRANSPORT_SCORE = 3
NOTABLE_MIN_AI_SCORE = 3
NOTABLE_MIN_GIS_SCORE = 3
SCORING_MODEL = "gpt-6.1-sol"      # used for scoring, digest and Esri search
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
    content: str | None = None

    transport_score: int | None = None
    transport_reason: str | None = None
    ai_score: int | None = None
    ai_reason: str | None = None
    gis_score: int | None = None
    gis_reason: str | None = None
    total_score: int | None = None     # combine_scores(), 0–65

    digest_status: str | None = None   # "qualified", "notable", "below threshold"
    published: bool = False
```

### Environment

- `uv`, Python 3.11 (`requires-python = ">=3.10"`)
- Corporate TLS: `uv sync --system-certs`, `uv add <package> --system-certs`
- Dependencies: `feedparser`, `openai`, `requests`, `beautifulsoup4`, `trafilatura`, plus unused `playwright`; `pydantic` used but not declared
- `OPENAI_API_KEY` from the environment; `.env` files are git-ignored
- Run modules with `-m`, e.g. `uv run python -m aimobility_news.main`

### Commit history

```text
f79346f Update README for transport, AI and GIS scoring
b73b3a0 Score on transport, AI and GIS; add debug digest and also-notable fill
1870815 Update README and checkpoint for AI x transport scoring and full-text work
6581a8e Score on AI x transport with full article text; add timing and new feeds
02807a8 Add v0.2 source adapters, relevance threshold, and fixed output path
ada1962 Update checkpoint for MVP v0.1 completion and add roadmap
b10c490 Reduce scoring.py __main__ to a single-article test
8a47bfa Build MVP v0.1 for AI mobility news digest
```

---

## Resume point

All work up to 2026-11-02 is committed and pushed: three-domain scoring, the qualified / notable / below-threshold classification, debug digest, README, this checkpoint, and the exploratory `aidailybrief_transcript.py`. Config still has test values (`RECENT_HOURS = 72`).

Next:

1. Finish AI Daily Brief full text (Markdown digest / transcript), then check full text for the new feeds.
2. Run several days, tune thresholds from the debug digests, and collect articles into the evaluation dataset.
3. Start v0.3: `llm.py` provider abstraction, explicit Ollama context window, then benchmark `qwen3.5:9b`, `qwen3:8b` and a ~14B model against OpenAI.

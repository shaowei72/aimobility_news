# AI Mobility News App — Checkpoint

_Last updated: 2026-11-03 — v0.3 wrapped up on OpenAI; Ollama benchmarking and the evaluation dataset deferred until the GPU is fixed_

## Project

`aimobility-news`  
Python package: `aimobility_news`  
Local folder: `E:\MyLocalDev\AIMobility\aimobility_news`  
Remote: https://github.com/shaowei72/aimobility_news

**Objective:** a personal AI-powered news intelligence system on **AI × land transport**, with particular interest in GeoAI, GIS, intelligent transport systems, and Singapore's transport landscape. It starts as an automated daily digest and is meant to grow into a locally powered, searchable news intelligence and research assistant.

The digest is a "Daily Briefing" with two sections: "Intelligent Transportation System (ITS)" and "AI Daily Brief". Articles are scored on three independent domains (transport, AI, GIS/GeoAI), combined so that transport plus AI and/or GIS ranks highest (section 2.3).

---

## Roadmap (revised 2026-11-03)

| Version | Focus | Status |
|---|---|---|
| **v0.1** | End-to-end MVP news pipeline | ✅ Complete |
| **v0.2** | Source coverage, full-text extraction and relevance scoring | 🚧 In progress |
| **v0.3** | Local LLM integration using Ollama | ✅ Wrapped up (2026-11-03); Ollama benchmark and evaluation dataset deferred (section 3.6) |
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

1. Finish the remaining v0.2 work (section 2.7): full text for the newer feeds, dedupe, tests, cleanup.
2. Stabilise the transport × AI × GIS scoring and daily digest quality; let the candidate pool grow from daily runs.
3. Fix the GPU crashes under Ollama (`docs/crash-investigation-2026-11-03.md`), then return to the deferred v0.3 items (section 3.6).
4. Start v0.4 (SQLite repository) when v0.2 is closed.

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

**Done in v0.3 (2026-11-03):** each edition is also published as Markdown, at `<edition_url>.md` (digest) and `<edition_url>/transcript.md` (podcast transcript). `aidailybrief_transcript.py` now splits each recent episode into individual stories, and the pipeline scores those stories instead of the edition teaser (section 3.5).

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
scoring call failed                                          → scoring failed
total_score ≥ MIN_TOTAL_SCORE                                → qualified
else AI Daily Brief story, AI ≥ AIDB_HEADLINES_MIN_AI_SCORE  → ai headline
else transport, AI or GIS ≥ its NOTABLE_MIN_*                → notable
else                                                         → below threshold
```

`select_for_digest()` publishes qualified then notable articles, highest total first, up to `TOP_RANKED` (8). Notable articles always score below `MIN_TOTAL_SCORE`, so qualified ones always come first. Fewer than 8 items are published when fewer are relevant. `select_ai_headlines()` separately publishes AI headlines, highest AI score first, up to `AIDB_HEADLINES_MAX` (4), so they never take one of the 8 slots.

- **Digest** (`output/digest-YYYY-MM-DD.md`), titled "Daily Briefing — date", in two sections, each numbered from 1:
  - **Intelligent Transportation System (ITS):** qualified articles, then notable ones under "Also notable (strong in one domain)". Each shows `Score: 15 (Transport 3, AI 3, GIS 0)`, a summary and "why it matters".
  - **AI Daily Brief** (after a horizontal rule): AI headlines with their AI score, the story splitter's summary (100–150 words, no extra LLM call) and a link to the story's place in the episode page.
  - Both headings always appear; an empty section says so ("No relevant ITS articles today.", "No AI Daily Brief stories today."). The AI Daily Brief section is often empty: episodes are not daily and are dated 23:59 UTC, so many 24-hour windows contain none. That is accepted.
- **Debug digest** (`output/debug-digest-YYYY-MM-DD.md`): every scored article, highest total first, with status (`qualified, published`, `notable, over max`, `ai headline, published`, `below threshold`, …), the three scores, the text it was scored on, the model that scored it, and all three reasons. No LLM calls.

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
- [x] AI Daily Brief: use the `.md` digest / `transcript.md` as full text; split editions into individual stories (done in v0.3, section 3.5)
- [ ] Separate source discovery from article extraction
- [ ] Check full-text availability for the new transport and AI feeds; add summary-only sources to `PAGE_FETCH_SOURCES` where pages extract cleanly
- [ ] Summarise published articles from the full webpage text instead of the RSS teaser (fetch only for the ≤ 8 published items; larger word cap for the digest than for scoring)
- [ ] Remove or replace The Robot Report (403)
- [ ] Continue searching for AI-in-transport / ITS / Singapore sources; consider per-source lookback windows for weekly sources

**Scoring and digest quality**
- [ ] Run several days and tune `MIN_TOTAL_SCORE` and `NOTABLE_MIN_*` from the debug digests. Current values are 11 and 3 / 3 / 3; `RECENT_HOURS = 24`
- [ ] Build the evaluation dataset: deferred with the Ollama benchmark (section 3.6); the candidate pool keeps collecting meanwhile

**Reliability**
- [ ] Deduplicate on normalised title and canonical URL (strip `utm_*`), not only exact URL
- [x] Wrap Esri and AI Daily Brief calls in `main.py` so an adapter failure does not abort the run
- [ ] Warn when the AI Daily Brief archive returns no editions at all (distinct from none in the time window)
- [ ] Esri search: restrict to `https://www.esri.com/arcgis-blog/` URLs; its model-written summary may inflate scores; it requests 7 days but most results are then filtered out
- [ ] Strip `script`, `style` and `figcaption` in `html_to_text()`
- [ ] Retry failed API calls (Ollama retries once on invalid JSON; HTTP errors and OpenAI calls are not retried)
- [ ] `validate_feeds.py`: reuse `load_feed()`; report dated, recent and full-text entries
- [ ] Add pytest tests with hand-built `Article` objects (filtering, dedupe, `combine_scores()`, classification, `extract_content()`, `text_for_scoring()`)

**Cleanup**
- [ ] Remove scratch code: `openAI.py`, `substack.py`, `src/geoai_signal_feed.xml` (225 KB, tracked), commented-out blocks
- [ ] Remove unused imports in `feeds.py` (`random`, `fetch_esri_articles`)
- [ ] Remove `playwright` from `pyproject.toml`; declare `pydantic`
- [ ] Regenerate `docs/sample-digest.md` (current sample is from v0.1)

---

## 3. v0.3 — Local LLM integration with Ollama (wrapped up 2026-11-03)

**Objective:** run the core LLM functions locally, reducing reliance on paid cloud inference.

**Exit criterion:** end-to-end digest generation using a local Ollama model for scoring and summarisation, with results comparable to the OpenAI-based pipeline.

**Outcome:** the code side is done and the pipeline can run on either provider. Ollama (`qwen3.5:9b`) ran end to end once on 2026-11-02. But on 2026-11-03 the PC crashed twice under Ollama: a PCIe hardware error, then `CUDA error: unknown error`, then the machine was powered off. The same prompt had succeeded earlier, which points to the GPU, its driver or its PCIe link rather than the code (`docs/crash-investigation-2026-11-03.md`). Development continues on OpenAI (the default, `LLM_PROVIDER = "openai"`). The "comparable results" half of the exit criterion needs the evaluation dataset and benchmark, which are deferred (section 3.6).

### 3.1 Environment (checked 2026-11-02)

| Item | Value |
|---|---|
| Ollama | 0.40.13, installed |
| Models pulled | `qwen3.5:9b` (6.6 GB), `qwen3:8b` (5.2 GB), `qwen3:4b` (2.6 GB) |
| GPU | NVIDIA RTX 5060 Ti, 16 GB VRAM |
| CPU / RAM | Intel i5-11400F, 64 GB |

8–9B models fit with room for a large context window; ~14B models fit at 4-bit quantisation.

### 3.2 Where the LLM is used

| File | Task (`LLM_MODELS`) | Use | Provider |
|---|---|---|---|
| `scoring.py` | `scoring` | transport / AI / GIS scores + reasons, one call per article | OpenAI or Ollama |
| `digest.py` | `digest` | summary + "why it matters", one call per published ITS article (≤ 8) | OpenAI or Ollama |
| `aidailybrief_transcript.py` | `transcript` | group an episode's headings into stories (one call per section), then summarise each story (one call per story); cached per episode and model | OpenAI or Ollama |
| `aidailybrief_transcript.py --compare` | `judge` | optional judge comparing per-story vs single-call summaries | OpenAI by default |
| `esri_search.py` | — | Esri discovery via OpenAI **web search** | OpenAI only (a local model cannot search the web); skipped with a warning if it fails |
| `openAI.py` | — | scratch | Remove |

Every call goes through `llm.parse(prompt, schema, task, label)`, which routes to `llm_openai.py` (Responses API structured output, client created on first use) or `llm_ollama.py` (native `/api/chat` with the Pydantic schema as `format`), and logs the call to `output/llm-calls.csv`.

### 3.3 Plan and status

Status: steps 1–3, 6 and 7 ✅ done (`059d259`, `e0fa29d`, this wrap-up); step 4 started (candidate pool, `5b35662`) then deferred; step 5 deferred. Details in 3.5 and 3.6. The original plan text follows.

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

### 3.5 Delivered

- **Provider switch** (`llm.py`, `llm_openai.py`, `llm_ollama.py`): `LLM_PROVIDER` plus `LLM_MODELS` per provider and task (`scoring`, `digest`, `transcript`, `judge`); `--provider {openai,ollama}` on `main.py` and `aidailybrief_transcript.py`. Prompts live with their callers, so both providers always get the same prompt.
- **Ollama settings:** explicit `OLLAMA_NUM_CTX = 16384` (warns if a prompt fills it), temperature 0, thinking off, one retry on invalid JSON.
- **Robustness:** scores bounded 0–5 in the schema; a failed scoring call marks the article "scoring failed" and the run continues (it stops only if every article fails); a failed summary shows "Summary unavailable"; Esri and AI Daily Brief failures skip the source.
- **Call log** (`output/llm-calls.csv`): one row per call: run, provider, model, task, label, status, attempts, prompt/output tokens, `num_ctx`, seconds.
- **Candidate pool** (`output/scored-articles.jsonl`): every run appends each scored article with the exact text the model saw, its scores, reasons, status and the code version, for the later evaluation dataset.
- **AI Daily Brief stories** (`aidailybrief_transcript.py`, `fetch_aidailybrief_stories()` in `aidailybrief.py`):
  1. Parse the episode's Markdown digest headings (Headlines and Main episode sections).
  2. Group headings into stories (LLM, one call per section).
  3. Cut each story's transcript excerpt by minute markers, ±1 minute (`AIDB_BUFFER_*_MIN`).
  4. Summarise each story: headline, 100–150-word summary, 3–6 key points (LLM).
  5. Save everything to `output/aidailybrief/<date>/stories__<provider>_<model>.json`; reruns reuse it (`--refresh` to redo).
  6. Optional `--compare`: single-call baseline and a judge's verdict.

  In `main.py`, each episode in the time window becomes one `Article` per story (summary + key points as full text, URL = the story's `#anchor` on the episode page), scored like any article. Episodes that cannot be split fall back to the edition teaser. A weekday news episode gives about 6 stories (29 Oct: 3 AI headlines at AI ≥ 3); a weekend essay episode is one story (1 Nov: AI 2, not published).
- **Digest format:** "Daily Briefing" with "Intelligent Transportation System (ITS)" and "AI Daily Brief" sections (section 2.4).

### 3.6 Deferred to-do (revisit after the GPU is fixed)

- [ ] **Fix the GPU crashes** under Ollama: clean-install or roll back the NVIDIA driver; reseat the card and check its power; try PCIe Gen 4 in the BIOS; watch `nvidia-smi -l 1` during a run; GPU stress test without Ollama. See `docs/crash-investigation-2026-11-03.md`.
- [ ] **Confirm stability:** repeat the 4,344-token "Intelligence Index V5" story summary (29 Oct episode) 10–20 times on Ollama from a fresh boot.
- [ ] **Guard:** stop the run after the first Ollama HTTP 500 instead of continuing on a CPU fallback.
- [ ] **Evaluation dataset** (step 4): draw 30–50 articles from the candidate pool (≈10 strong overlap, ≈10 borderline around `MIN_TOTAL_SCORE`, ≈10 single-domain, 5–10 low; include summary-only and a few AI Daily Brief stories), freeze them with their text in a tracked file, and hand-label at least the borderline ones. As of 2026-11-03 the pool held only 31 unique articles (2 strong overlap, 2 borderline).
- [ ] **Benchmark** (step 5): `qwen3.5:9b`, `qwen3:8b` and a ~14B model against OpenAI on the frozen set. Compare at "differs by more than 1", not exact match: OpenAI itself changed 3 of 23 re-scored articles by 1 point on identical text, one of them across the notable threshold.
- [ ] **Exit criterion:** a full digest run on Ollama with results comparable to OpenAI.

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
- **Keep the LLM behind one function.** With `llm.parse()` and per-task models, switching provider is a config change, and the call log makes runs comparable.
- **Local inference depends on the hardware being stable.** Sustained GPU load exposed a GPU/driver/PCIe fault that crashed the PC; keep the cloud provider as the default until local runs are proven stable.
- **The reference model is not deterministic.** OpenAI changed 1 in 8 re-scored articles by a point on identical text, so benchmarks need a tolerance and hand labels near the threshold.
- **A podcast's published outline is a good scaffold for splitting it.** Grouping the outline's talking points into stories, then cutting the transcript by its minute markers, is cheaper and more reliable than asking a model to split a whole transcript.
- **Give a broad source its own digest section.** AI-only stories cannot reach the transport-weighted threshold, and boosting their score would push out the transport news; a separate capped section keeps both.

---

## Reference

### Current pipeline

```text
RSS feeds (FEEDS) ---------------------\
Esri search (OpenAI web search) --------→ Article objects
AI Daily Brief stories ----------------/
  (recent episodes split into stories by aidailybrief_transcript.build_stories(), cached)

→ filter_recent_articles()     last RECENT_HOURS; undated articles dropped
→ deduplicate_articles()       exact URL
→ add_page_content()           webpage full text for PAGE_FETCH_SOURCES
→ score_articles()             llm.parse(): transport, AI, GIS (0–5) + reasons
                               total = (T + 1) × (A + G + 1) − 1
→ rank_articles()              total_score, descending
→ classify_articles()          qualified / ai headline / notable / below threshold / scoring failed
→ select_for_digest()          ITS: qualified then notable, up to TOP_RANKED
→ select_ai_headlines()        AI Daily Brief: highest AI score, up to AIDB_HEADLINES_MAX
→ generate_digest()            ITS: LLM summary + "why it matters"; AI Daily Brief: stored story summary
→ generate_debug_digest()      all scored articles, scores and reasons (no LLM)
→ save_digest(), save_to_pool() output/digest-*.md, output/debug-digest-*.md, output/scored-articles.jsonl
→ timing summary               (every LLM call also logged to output/llm-calls.csv)
```

### Configuration (`config.py`)

```python
FEEDS = {**FEEDS_transport, **FEEDS_AI, **FEEDS_gis}
RECENT_HOURS = 24
MIN_TOTAL_SCORE = 11               # on the 0–65 scale
NOTABLE_MIN_TRANSPORT_SCORE = 3
NOTABLE_MIN_AI_SCORE = 3
NOTABLE_MIN_GIS_SCORE = 3
TOP_RANKED = 8

LLM_PROVIDER = "openai"            # or "ollama"; --provider overrides
OPENAI_MODEL = "gpt-6.1-sol"       # also used by Esri search
LLM_MODELS = {"openai": {...}, "ollama": {...}}   # per task: scoring, digest, transcript, judge
OLLAMA_NUM_CTX = 16384             # plus OLLAMA_HOST, _TEMPERATURE (0), _THINK (False), _TIMEOUT, _MAX_ATTEMPTS
LLM_CALL_LOG = "output/llm-calls.csv"
SCORED_POOL = "output/scored-articles.jsonl"

AIDB_DIR = "output/aidailybrief"
AIDB_BUFFER_BEFORE_MIN = 1         # transcript excerpt buffer, minutes
AIDB_BUFFER_AFTER_MIN = 1
AIDB_SOURCE = "AI Daily Brief"
AIDB_HEADLINES_MAX = 4
AIDB_HEADLINES_MIN_AI_SCORE = 3

MAX_CONTENT_WORDS = 1500
FULL_TEXT_MIN_WORDS = 150
PAGE_FETCH_SOURCES = {"Google Research", "Google DeepMind", "Hugging Face Blog"}
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
    scored_by: str | None = None       # provider:model
    scoring_error: str | None = None   # set when the scoring call failed

    digest_status: str | None = None   # "qualified", "ai headline", "notable", "below threshold", "scoring failed"
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
5b35662 Save scored articles to a candidate pool for the evaluation dataset
6f6d822 Update validate_feeds.py
e0fa29d Log LLM calls to CSV; bound scores 0-5 and survive failed calls (v0.3 steps 2-3)
059d259 Add switchable LLM provider: OpenAI or local Ollama (v0.3 start)
44da52b Classify articles as qualified, notable or below threshold; revise roadmap
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

v0.3 is wrapped up and all work up to 2026-11-03 is committed and pushed: the provider switch, call log, candidate pool, AI Daily Brief story splitting, the two-section digest, and the GPU crash investigation. Runs use OpenAI; `RECENT_HOURS = 24`.

Next:

1. Remaining v0.2 work (section 2.7): full text for the newer feeds, better dedupe, pytest tests, cleanup.
2. Run daily, tune thresholds from the debug digests, and let the candidate pool grow.
3. Fix the GPU, then the deferred v0.3 items (section 3.6): evaluation dataset, Ollama benchmark, Ollama exit criterion.
4. v0.4: SQLite repository.

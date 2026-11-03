# AI Mobility News

MVP v0.4 (SQLite news repository); v0.5 (WhatsApp-ready digest) next

Daily AI-powered news digest on AI and GIS applied to land transport
(Intelligent Transportation Systems), with a separate section of the day's
general AI news from the AI Daily Brief podcast.

## What it does

- Pulls articles from configured RSS feeds, the Esri ArcGIS Blog (via OpenAI
  web search) and the AI Daily Brief podcast
- Splits each recent AI Daily Brief episode into individual news stories,
  using the episode's published outline and transcript
- Filters to recent articles and deduplicates by URL
- Uses the full article text where available: from the feed itself, or by
  fetching the article webpage for selected sources
- Scores each article with an LLM on three independent 0–5 criteria (land
  transport, AI, GIS/GeoAI) and combines them so that transport combined
  with AI and/or GIS ranks highest
- Publishes a two-section **Daily Briefing**:
  - **Intelligent Transportation System (ITS):** articles at or above a
    minimum score, up to a configurable Top N, plus "Also notable" articles
    strong in one domain on thin days; each with a short summary and "why it
    matters"
  - **AI Daily Brief:** the strongest AI stories from the podcast, ranked by
    AI score, with their own cap so they never take an ITS slot
- Saves the digest as Markdown, plus a debug digest listing every scored
  article with its scores and reasons, and prints step timings
- Stores every run in a SQLite database: articles, every score with the
  exact text the model saw, the published summaries, digest status and the
  AI Daily Brief story splits; an article the same model has already scored
  on an identical prompt is not scored again
- Reads past digests back from the database into one Markdown file, by day
  (`reader.py`), and backfills past AI Daily Brief episodes (`backfill_aidb.py`)
- Runs on OpenAI or on a local model via Ollama (switchable per run), and
  logs every LLM call to a CSV file

## Current pipeline

```text
RSS feeds + Esri search + AI Daily Brief stories
→ recent articles
→ deduplicate
→ fetch article pages (PAGE_FETCH_SOURCES only)
→ reuse stored scores for identical prompts
→ LLM scoring (transport, AI, GIS → total_score)
→ classify: qualified / AI headline / notable / below threshold
→ ITS section: qualified, then "Also notable", up to TOP_RANKED
→ AI Daily Brief section: AI headlines, up to AIDB_HEADLINES_MAX
→ summaries for the ITS articles
→ Markdown output (digest + debug digest), LLM call log
→ database: articles, scores, summaries, digest status
```

## Scoring

Each article gets three integer scores from 0 to 5, each with a one-sentence
reason. The domains are scored independently, on relevance and significance:

| Level | Meaning (all three domains) |
|---|---|
| 0 | No meaningful content in the domain |
| 1 | Incidental mention or marketing buzzword |
| 2 | Routine or general news |
| 3 | Substantive development or concrete application |
| 4 | Significant advance, innovation or deployment |
| 5 | Highly consequential development or breakthrough |

- `transport_score`: land transport (roads, rail, buses, AVs, micromobility,
  freight, planning, policy), with particular interest in Singapore and ITS;
  aviation and maritime only for land-side connections
- `ai_score`: AI technology, research, applications and governance
- `gis_score`: GIS, geospatial data, remote sensing, positioning, digital
  twins and GeoAI

The scores are combined as:

```text
total_score = (transport + 1) × (ai + gis + 1) − 1        # 0–65
```

A single domain scores at most 5, and AI + GIS without transport at most 10.
Transport combined with AI and/or GIS multiplies:

| Transport / AI / GIS | Total |
|---|---|
| 5 / 5 / 5 | 65 |
| 4 / 4 / 0 | 24 |
| 3 / 3 / 0 | 15 |
| 2 / 3 / 0 | 11 |
| 0 / 5 / 5 | 10 |
| 0 / 5 / 0 | 5 |

With `MIN_TOTAL_SCORE = 11`, an article needs a transport link plus AI or GIS
content to qualify for the ITS section. An AI Daily Brief story that does not
qualify becomes an "AI headline" if its AI score is at least
`AIDB_HEADLINES_MIN_AI_SCORE` (3). The full rubric is in
`src/aimobility_news/scoring.py`.

## AI Daily Brief stories

Each episode is published as a Markdown outline (one `###` heading per
talking point, with its minute in the episode) and a transcript with minute
markers. `aidailybrief_transcript.py`:

1. parses the outline's Headlines and Main episode headings
2. groups the headings into stories (one LLM call per section)
3. cuts each story's part of the transcript, with a 1-minute buffer each side
4. summarises each story: headline, 100–150-word summary, key points (one
   LLM call per story)
5. saves the result in the database (`aidb_story_sets`, one per episode and
   model), which later runs reuse

The pipeline does this for every episode in the time window. Episodes are not
published every day, so the AI Daily Brief section is sometimes empty.
`backfill_aidb.py` does the same for a range of past episodes, committing per
episode so an interrupted run resumes where it stopped.

## Database

`output/db/news.db` (SQLite, git-ignored; `db.py`):

| Table | One row per |
|---|---|
| `runs` | pipeline, backfill or import run, with code version and settings |
| `articles` | URL: title, source, published date, feed summary, longest full text |
| `scores` | scoring: model, prompt hash, exact text, scores, reasons, error |
| `summaries` | digest summary of a published ITS article: model, prompt hash, summary, why it matters |
| `digest_items` | run × article: digest status, published, section, score and summary used |
| `aidb_episodes` | AI Daily Brief episode: date, title, lead |
| `aidb_story_sets` | episode × model: the full story split as JSON |

A stored score is reused when the same model has already scored an identical
prompt (same rubric, title and text). Summaries are stored but not reused, as
only same-day re-runs would benefit (`db.reuse_summaries()` is commented out,
ready to enable).

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.10+.

```powershell
uv sync --system-certs
```

`--system-certs` makes uv use the Windows certificate store, which is needed
on networks with corporate TLS inspection. Elsewhere, plain `uv sync` works.

Set your OpenAI API key (used for scoring, summaries, AI Daily Brief stories
and Esri search):

```powershell
$env:OPENAI_API_KEY = "sk-..."
```

Optional, for local models: install [Ollama](https://ollama.com/) and pull
the model set in `LLM_MODELS`, e.g. `ollama pull qwen3.5:9b`.

> **Note:** on the development PC, Ollama runs have crashed the machine
> (GPU/driver/PCIe fault under load; see
> [`docs/crash-investigation-2026-11-03.md`](docs/crash-investigation-2026-11-03.md)).
> OpenAI is the default until that is fixed.

## Usage

Run modules with `-m` (the package uses relative imports, so running files by
path will fail):

```powershell
# Run the full pipeline; writes output/digest-YYYY-MM-DD.md and
# output/debug-digest-YYYY-MM-DD.md
uv run python -m aimobility_news.main

# Same, with a local Ollama model instead of OpenAI
uv run python -m aimobility_news.main --provider ollama

# Split AI Daily Brief episodes into stories (by date, or the latest N);
# --refresh reruns the LLM steps, --compare adds a single-call baseline
# and a judge's comparison
uv run python -m aimobility_news.aidailybrief_transcript 2026-10-29
uv run python -m aimobility_news.aidailybrief_transcript --latest 3

# Backfill past AI Daily Brief episodes into the database (resumable;
# --dry-run lists what is already stored)
uv run python -m aimobility_news.backfill_aidb --since 2026-10-01 --until 2026-10-31 --provider openai

# Read stored digests back, by day, newest first (default: last 7 days);
# its or aidb for one source only; --all adds unpublished ITS articles and
# scoring reasons; --min-ai-score filters AI Daily Brief stories
uv run python -m aimobility_news.reader --since 2026-10-01
uv run python -m aimobility_news.reader aidb --min-ai-score 4

# Database table counts
uv run python -m aimobility_news.db --stats

# Check that each configured RSS feed is reachable and parseable
uv run python -m aimobility_news.validate_feeds

# Score a single test article (one LLM call)
uv run python -m aimobility_news.scoring

# Run the tests (temporary database, fake LLM: no API calls, news.db untouched)
uv run pytest -q

# Test the source adapters
uv run python -m aimobility_news.aidailybrief
uv run python -m aimobility_news.esri_search     # uses OpenAI web search
```

All output goes to `output/`, which is git-ignored:

| File | Contents |
|---|---|
| `digest-YYYY-MM-DD.md` | The Daily Briefing. Same-day reruns are saved as `(1)`, `(2)`, … |
| `debug-digest-YYYY-MM-DD.md` | Every scored article: status, total, transport, AI, GIS, the model that scored it, and the reasons; for tuning the threshold and rubric |
| `db/news.db` | The SQLite news repository (see [Database](#database)) |
| `reader/<section or all>-<since>_<until>.md` | Output of `reader.py` |
| `llm-calls.csv` | One row per LLM call: provider, model, task, status, tokens, seconds |
| `aidailybrief/<date>/` | Each episode's outline and transcript, plus `--compare` files |

See [`docs/sample-digest.md`](docs/sample-digest.md) for an example (from
v0.1; the format has changed since).

## Configuration

All settings are in `src/aimobility_news/config.py`:

| Setting | Purpose |
|---|---|
| `FEEDS` | Active RSS feeds: `FEEDS_transport`, `FEEDS_AI` and `FEEDS_gis` merged |
| `RECENT_HOURS` | Freshness window (24) |
| `MIN_TOTAL_SCORE` | Minimum `total_score` for the ITS section (11) |
| `TOP_RANKED` | Maximum number of ITS items (8) |
| `NOTABLE_MIN_TRANSPORT_SCORE`, `NOTABLE_MIN_AI_SCORE`, `NOTABLE_MIN_GIS_SCORE` | Single-domain minimums for "Also notable" (3, 3, 3) |
| `AIDB_HEADLINES_MAX` | Maximum number of AI Daily Brief items (4) |
| `AIDB_HEADLINES_MIN_AI_SCORE` | Minimum AI score for an AI Daily Brief item (3) |
| `AIDB_BUFFER_BEFORE_MIN`, `AIDB_BUFFER_AFTER_MIN` | Minutes of transcript added around each story (1, 1) |
| `LLM_PROVIDER` | `"openai"` (default) or `"ollama"`; `--provider` overrides it for a run |
| `LLM_MODELS` | Model per provider and task (`scoring`, `digest`, `transcript`, `judge`) |
| `OPENAI_MODEL` | OpenAI model, also used for Esri search |
| `OLLAMA_*` | Ollama host, context window (`OLLAMA_NUM_CTX`, 16384), temperature, thinking, timeout, retries |
| `LLM_CALL_LOG` | Path of the LLM call log (`None` disables) |
| `DB_FILE` | Path of the SQLite database (`output/db/news.db`) |
| `MAX_CONTENT_WORDS` | Cap on article words sent to the LLM |
| `FULL_TEXT_MIN_WORDS` | Minimum length for text to count as the full article |
| `PAGE_FETCH_SOURCES` | Sources whose article webpages are fetched for full text |

## Layout

```text
src/aimobility_news/
├── main.py                       # pipeline entry point, step timing
├── config.py                     # feeds and settings
├── models.py                     # Article dataclass
├── feeds.py                      # RSS fetch, full-text extraction, page fetch, filter, dedupe
├── aidailybrief.py               # AI Daily Brief archive scraper; episodes -> story articles
├── aidailybrief_transcript.py    # split an episode into stories (outline + transcript)
├── esri_search.py                # Esri ArcGIS Blog via OpenAI web search
├── llm.py                        # provider switch and LLM call log
├── llm_openai.py                 # OpenAI structured output
├── llm_ollama.py                 # Ollama structured output (native API)
├── scoring.py                    # relevance scoring (transport, AI, GIS)
├── ranking.py                    # sort, classify, select ITS and AI Daily Brief items
├── digest.py                     # summaries, Markdown digest and debug digest -> output/
├── db.py                         # SQLite repository: schema, save, score reuse, --stats
├── backfill_aidb.py              # backfill past AI Daily Brief episodes into the database
├── reader.py                     # stored digests -> one Markdown file by day (standalone, read-only)
└── validate_feeds.py             # feed health check

tests/
├── conftest.py                   # temporary database, fake LLM, article helper
└── test_db.py                    # repository, score reuse, summaries, import, backfill resume
```

See `aimobility-news-checkpoint.md` for detailed progress notes, the roadmap,
v0.4 status and deferred work (local-model benchmark and evaluation dataset).

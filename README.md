# AI Mobility News

MVP v0.2 (in progress)

Daily AI-powered news digest on AI and GIS applied to land transport, with
emphasis on GeoAI and the use of GIS in transport.

## What it does

- Pulls articles from configured RSS feeds and two source adapters
  (Esri ArcGIS Blog via OpenAI web search, AI Daily Brief archive scraper)
- Filters to recent articles and deduplicates by URL
- Uses the full article text where available: from the feed itself, or by
  fetching the article webpage for selected sources
- Scores each article with an OpenAI model on three independent 0–5
  criteria (land transport, AI, GIS/GeoAI) and combines them so that
  transport combined with AI and/or GIS ranks highest
- Keeps articles at or above a minimum score, up to a configurable Top N
- On thin days, fills remaining slots with articles strong in one domain
  ("Also notable")
- Generates a short summary and "why it matters" for each selected article
- Saves the daily digest as Markdown, plus a debug digest listing every
  scored article with its scores and reasons, and prints step timings

## Current pipeline

```text
RSS feeds + Esri search + AI Daily Brief
→ recent articles
→ deduplicate
→ fetch article pages (PAGE_FETCH_SOURCES only)
→ AI scoring (transport, AI, GIS → total_score)
→ ranking + MIN_TOTAL_SCORE threshold
→ Top N, plus "Also notable" if fewer than Top N qualify
→ digest generation
→ Markdown output (digest + debug digest)
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
content. The full rubric is in `src/aimobility_news/scoring.py`.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.10+.

```powershell
uv sync --system-certs
```

`--system-certs` makes uv use the Windows certificate store, which is needed
on networks with corporate TLS inspection. Elsewhere, plain `uv sync` works.

Set your OpenAI API key (used for scoring, digest generation and Esri search):

```powershell
$env:OPENAI_API_KEY = "sk-..."
```

## Usage

Run modules with `-m` (the package uses relative imports, so running files by
path will fail):

```powershell
# Run the full pipeline; writes output/digest-YYYY-MM-DD.md and
# output/debug-digest-YYYY-MM-DD.md
uv run python -m aimobility_news.main

# Check that each configured RSS feed is reachable and parseable
uv run python -m aimobility_news.validate_feeds

# Score a single test article (one OpenAI call)
uv run python -m aimobility_news.scoring

# Test the source adapters
uv run python -m aimobility_news.aidailybrief
uv run python -m aimobility_news.esri_search     # uses OpenAI web search
```

Digests are written to `output/`, which is git-ignored. Same-day reruns are
saved as `digest-YYYY-MM-DD(1).md`, `(2)`, and so on. The debug digest has
a table of every scored article (status, total, transport, AI, GIS) followed
by each article's reasons, for tuning the threshold and rubric. See
[`docs/sample-digest.md`](docs/sample-digest.md) for an example (from v0.1).

## Configuration

All settings are in `src/aimobility_news/config.py`:

| Setting | Purpose |
|---|---|
| `FEEDS` | Active RSS feeds: `FEEDS_transport`, `FEEDS_AI` and `FEEDS_gis` merged |
| `RECENT_HOURS` | Freshness window (24) |
| `MIN_TOTAL_SCORE` | Minimum `total_score` for the digest (11) |
| `TOP_RANKED` | Maximum number of digest items (8) |
| `NOTABLE_MIN_TRANSPORT_SCORE`, `NOTABLE_MIN_AI_SCORE`, `NOTABLE_MIN_GIS_SCORE` | Single-domain minimums for "Also notable" (2, 3, 3) |
| `SCORING_MODEL` | OpenAI model for scoring, digest and Esri search |
| `MAX_CONTENT_WORDS` | Cap on article words sent to the LLM |
| `FULL_TEXT_MIN_WORDS` | Minimum length for text to count as the full article |
| `PAGE_FETCH_SOURCES` | Sources whose article webpages are fetched for full text |

## Layout

```text
src/aimobility_news/
├── main.py             # pipeline entry point, step timing
├── config.py           # feeds and settings
├── models.py           # Article dataclass
├── feeds.py            # RSS fetch, full-text extraction, page fetch, filter, dedupe
├── aidailybrief.py     # AI Daily Brief archive scraper
├── esri_search.py      # Esri ArcGIS Blog via OpenAI web search
├── scoring.py          # OpenAI relevance scoring (transport, AI, GIS)
├── ranking.py          # sort by total score, "Also notable" selection
├── digest.py           # summaries, Markdown digest and debug digest -> output/
└── validate_feeds.py   # feed health check
```

See `aimobility-news-checkpoint.md` for detailed progress notes and next steps.

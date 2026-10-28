# AI Mobility News

MVP v0.2 (in progress)

Daily AI-powered news digest on AI applied to land transport, with emphasis
on GeoAI and the use of GIS in transport.

## What it does

- Pulls articles from configured RSS feeds and two source adapters
  (Esri ArcGIS Blog via OpenAI web search, AI Daily Brief archive scraper)
- Filters to recent articles and deduplicates by URL
- Uses the full article text where available: from the feed itself, or by
  fetching the article webpage for selected sources
- Scores each article with an OpenAI model on two 0–5 criteria, AI and land
  transport, and ranks by their product
- Keeps articles at or above a minimum score, up to a configurable Top N
- Generates a short summary and "why it matters" for each selected article
- Saves the daily digest as Markdown and prints how long each step took

## Current pipeline

```text
RSS feeds + Esri search + AI Daily Brief
→ recent articles
→ deduplicate
→ fetch article pages (PAGE_FETCH_SOURCES only)
→ AI scoring (ai_score × transport_score)
→ ranking + MIN_TOTAL_SCORE threshold
→ Top N
→ digest generation
→ Markdown output
```

## Scoring

Each article gets two integer scores from 0 to 5, each with a one-sentence
reason:

- `ai_score`: 0–3 for no AI up to a concrete non-spatial AI application;
  4–5 reserved for GeoAI (AI applied to imagery, LiDAR, GPS trajectories,
  maps, digital twins, GIS platforms)
- `transport_score`: 0–3 for no land transport up to substantive planning,
  operations or policy; 4–5 reserved for spatial data and GIS in transport

`total_score = ai_score × transport_score` (0–25). An article must be
relevant to both themes to score above 0. The full rubric and borderline
guidance are in `src/aimobility_news/scoring.py`.

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
# Run the full pipeline and write output/digest-YYYY-MM-DD.md
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
saved as `digest-YYYY-MM-DD(1).md`, `(2)`, and so on. See
[`docs/sample-digest.md`](docs/sample-digest.md) for an example (from v0.1).

## Configuration

All settings are in `src/aimobility_news/config.py`:

| Setting | Purpose |
|---|---|
| `FEEDS` | Active RSS feeds (currently set to `FEEDS_NEW`) |
| `RECENT_HOURS` | Freshness window |
| `MIN_TOTAL_SCORE` | Minimum `ai × transport` score for the digest |
| `TOP_RANKED` | Maximum number of digest items |
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
├── scoring.py          # OpenAI relevance scoring (AI × transport)
├── ranking.py          # sort by total score
├── digest.py           # summaries and Markdown digest -> output/
└── validate_feeds.py   # feed health check
```

See `aimobility-news-checkpoint.md` for detailed progress notes and next steps.

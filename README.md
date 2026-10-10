# AI Mobility News

MVP v0.1

Daily AI-powered news digest focused on GeoAI, GIS, and land transport.

## What it does

- Pulls articles from configured RSS feeds
- Filters to recent articles
- Deduplicates by URL
- Scores relevance to AI, GeoAI, and land transport using GPT-6.1 Sol
- Ranks articles using a combined relevance score
- Selects the Top 5
- Generates a short summary and "why it matters"
- Saves the daily digest as Markdown

## Current pipeline

```text
RSS feeds
→ recent articles
→ deduplicate
→ AI scoring
→ ranking
→ Top 5
→ digest generation
→ Markdown output
```

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.10+.

```powershell
uv sync --system-certs
```

`--system-certs` makes uv use the Windows certificate store, which is needed
on networks with corporate TLS inspection. Elsewhere, plain `uv sync` works.

Set your OpenAI API key (used for scoring and digest generation):

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

# Fetch, filter, and deduplicate feeds, then print a sample of articles
uv run python -m aimobility_news.feeds
```

Settings such as the feed list, time window (`RECENT_HOURS`), and model
(`SCORING_MODEL`) are in `src/aimobility_news/config.py`.

## Layout

```text
src/aimobility_news/
├── main.py             # pipeline entry point
├── config.py           # FEEDS, RECENT_HOURS, SCORING_MODEL
├── models.py           # Article dataclass
├── feeds.py            # fetch, filter recent, deduplicate
├── scoring.py          # OpenAI relevance scoring
├── ranking.py          # sort by total score
├── digest.py           # summaries and Markdown digest -> output/
└── validate_feeds.py   # feed health check
```

See `aimobility-news-checkpoint.md` for detailed progress notes and next steps.

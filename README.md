# aimobility-news

AI Mobility News aggregator: a daily news digest focused on GeoAI / GIS and AI
applied to land transport.

## Status

Early MVP. RSS ingestion and normalisation into `Article` objects work.
Filtering, deduplication, relevance scoring, ranking, SQLite storage, and
digest generation are not yet implemented. See
`aimobility-news-checkpoint.md` for detailed progress notes.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.10+.

```powershell
uv sync
```

On networks with corporate TLS inspection, use the system certificate store:

```powershell
uv sync --system-certs
```

## Usage

Run modules with `-m` (the package uses relative imports, so running files by
path will fail):

```powershell
# Check that each configured RSS feed is reachable and parseable
uv run python -m aimobility_news.validate_feeds

# Fetch all feeds and print a sample of articles
uv run python -m aimobility_news.feeds
```

## Layout

```text
src/aimobility_news/
├── config.py           # RSS feed list (single source of truth)
├── models.py           # Article dataclass
├── feeds.py            # fetch_articles(): RSS -> Article objects
└── validate_feeds.py   # feed health check
```

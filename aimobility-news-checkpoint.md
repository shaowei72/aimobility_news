# AI Mobility News App — Checkpoint

_Last updated: 2026-10-09_

## Project name

`aimobility-news`  
Python package: `aimobility_news`  
Local folder: `E:\MyLocalDev\AIMobility\aimobility_news`

## Goal

Build a daily AI-powered news intelligence app focused on:

- GeoAI / GIS
- AI applied to land transport
- Developments relevant to transport authorities, operators, planners, and geospatial teams

## MVP scope

The first version should:

- Collect recent articles from a small set of RSS feeds
- Normalise them into a common article structure
- Deduplicate
- Score relevance
- Rank and select a Top 5
- Generate a WhatsApp-friendly digest
- Store articles and scores in SQLite
- Save the daily digest as Markdown

For now, agent frameworks, RAG, vector databases, advanced UI, and automatic WhatsApp sending remain out of scope.

## Current project structure

```text
aimobility_news/
├── .gitignore
├── pyproject.toml
├── README.md
├── uv.lock
├── aimobility-news-checkpoint.md
├── .venv/                      (local only, git-ignored)
└── src/
    └── aimobility_news/
        ├── __init__.py
        ├── config.py
        ├── models.py
        ├── feeds.py
        └── validate_feeds.py
```

## Environment setup

- `uv` 0.12.24 installed
- Python 3.11.1 (`requires-python = ">=3.10"`)
- Virtual environment created with `uv sync`
- Corporate TLS issue resolved by telling uv to use the Windows/system certificate store:

```powershell
uv sync --system-certs
uv add <package> --system-certs
```

- Older `--native-tls` flag is deprecated in current uv; use `--system-certs`

Installed and pinned in `uv.lock`:

- `feedparser==6.0.14`
- `feedparser-sgmllib==2.1.0`

## Repository housekeeping

- Git repository on `main`
- `.gitignore` covers virtual environments, caches, secrets, logs, OS files, build artefacts, and `*.egg-info/`
- Previously tracked `src/aimobility_news.egg-info/` was removed from Git tracking

## RSS validation work completed

`validate_feeds.py` was created to test candidate RSS feeds.

It reports:

- HTTP status
- Whether parsing failed (`feedparser`'s `bozo` flag)
- Number of entries
- Error details if parsing failed
- Latest article title
- Publication date
- Article link

Run as a package module:

```powershell
uv run python -m aimobility_news.validate_feeds
```

This is important because the project now uses relative imports such as:

```python
from .config import FEEDS
```

Running the file directly by path causes:

```text
ImportError: attempted relative import with no known parent package
```

## Shared feed configuration

The feed dictionary was moved out of `validate_feeds.py` into a shared configuration file:

```text
src/aimobility_news/config.py
```

Both `validate_feeds.py` and `feeds.py` now import the same source of truth:

```python
from .config import FEEDS
```

This avoids maintaining duplicate feed lists.

## Current feed set and validation results

### Keep

**GIM International**

```text
HTTP status: 301
Parse error: False
Entries: 100
Latest: PwC and Esri to harness geospatial AI together
Result: OK
```

**Geospatial World**

```text
HTTP status: 301
Parse error: False
Entries: 10
Result: OK
```

**Open Geospatial Consortium**

```text
HTTP status: 301
Parse error: False
Entries: 10
Result: OK
```

### Keep for now

**QGIS Blog**

```text
HTTP status: 301
Parse error: False
Entries: 10
Result: OK
```

**Planet OSGeo**

```text
HTTP status: 301
Parse error: True
Entries: 40
Error: document declared as us-ascii, but parsed as utf-8
Result: WARN
```

The warning is non-fatal because entries are still returned.

**Smart Cities Dive**

```text
HTTP status: 200
Parse error: False
Entries: 10
Result: OK
```

This feed is broad and may contain irrelevant items, which is useful later for testing AI relevance filtering.

### Drop / revisit later

**Esri ArcGIS Blog**

```text
HTTP status: 403
Entries: 0
Result: FAIL
```

**ITS International**

```text
HTTP status: 404
Entries: 0
Result: FAIL
```

**Sustainable Bus - ITS**

```text
HTTP status: 301
Parse error: True
Entries: 0
Result: FAIL
```

**Railway Gazette - Metro**

```text
HTTP status: 404
Parse error: True
Entries: 0
Result: FAIL
```

## Key source-design learning

A valuable news source does not necessarily have a usable RSS feed.

Sources such as Esri or ITS International may still be useful later through another ingestion method, but the MVP will proceed first with feeds that work reliably.

The current source mix is stronger on GIS/geospatial than land transport. This is acceptable for the next development step, though stronger land-transport feeds should be added later.

## Article data model created

Created:

```text
src/aimobility_news/models.py
```

Current model:

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Article:
    title: str
    url: str
    source: str
    published_at: datetime | None
    summary: str | None
```

Conceptually, `Article` is the common application-level representation of a news item.

The purpose is to convert feed-specific data into one consistent structure so downstream code does not need to know which RSS source an article came from.

## RSS ingestion module created

Created:

```text
src/aimobility_news/feeds.py
```

Current responsibility:

```text
RSS feeds
   ↓
feedparser entries
   ↓
convert
   ↓
Article objects
```

`fetch_articles()`:

- loops through all configured feeds
- parses each feed
- converts each entry into an `Article`
- returns a list of `Article` objects

Run with:

```powershell
uv run python -m aimobility_news.feeds
```

## Publication date handling

Initially, every article used:

```python
published_at=None
```

This has now been improved to use `feedparser`'s parsed publication date where available:

```python
from datetime import datetime, timezone

published_at = None

if entry.get("published_parsed"):
    published_at = datetime(
        *entry.published_parsed[:6],
        tzinfo=timezone.utc
    )
```

The resulting `datetime` is stored in the `Article.published_at` field.

This prepares the project for the next important feature: filtering to recent articles.

## Temporary test output

`feeds.py` includes a temporary test block under:

```python
if __name__ == "__main__":
```

It currently:

- fetches all articles
- prints the total number fetched
- randomly selects up to 10 articles
- prints key fields for inspection

Random sampling uses:

```python
import random

for article in random.sample(articles, min(10, len(articles))):
    ...
```

This helps inspect articles from different feeds rather than always seeing the first few entries from the same source.

## Current stage

The project has now moved beyond RSS validation into basic ingestion and normalisation.

Completed:

```text
environment setup
→ feed validation
→ shared feed configuration
→ Article model
→ RSS ingestion
→ publication date parsing
```

## Next step

The next coding task should be:

```text
filter fetched articles to a recent time window
```

Recommended first implementation:

```text
fetch all configured feeds
→ convert to Article objects
→ keep only articles published in the last 24 hours
```

This will require:

- obtaining the current UTC time
- comparing `article.published_at` against a cutoff time
- deciding what to do with articles whose `published_at` is `None`

After this works, the next likely steps are:

```text
last-24-hours filtering
→ basic deduplication
→ AI relevance scoring
→ Top 5 ranking
```

SQLite storage should come after the ingestion and filtering logic is behaving reliably.

## Resume point

Continue with **filtering `Article` objects to the last 24 hours**, while handling missing publication dates sensibly.

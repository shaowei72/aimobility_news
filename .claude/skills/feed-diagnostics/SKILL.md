---
name: feed-diagnostics
description: Diagnose RSS feed content completeness — classify each source as RSS_COMPLETE, PAGE_FETCH_REQUIRED, MIXED or INCONCLUSIVE and recommend the cheapest reliable way to get full article text. Use when evaluating a new or existing feed, or deciding whether a source belongs in PAGE_FETCH_SOURCES.
---

## RSS Content Completeness Classification

The primary objective of feed-diagnostics is to
determine the least expensive reliable method of
obtaining complete article text.

For each RSS source, sample 5-10 recent entries,
where available. Include articles of different
lengths, categories and publication dates.

For each sampled article:

1. Retrieve title, description, content:encoded
   and other relevant RSS content fields.
2. Clean HTML markup without losing meaningful text.
3. Fetch the corresponding article webpage.
4. Extract the main body using trafilatura.
5. If extraction is incomplete, inspect the HTML
   structure and selectively test Playwright.
6. Compare the RSS text against the extracted
   webpage text and original visible article.
7. Check for missing paragraphs, truncated endings,
   duplicated text and irrelevant boilerplate.
8. Record whether full content is demonstrably
   available from RSS, webpage or neither.

Do not use character count alone as proof of
completeness. Apply semantic and structural
comparisons, including beginning, middle and ending
paragraphs.

### Article Classification

Assign one classification per article:

RSS_COMPLETE:
  The RSS contains the complete substantive article.

PAGE_FETCH_REQUIRED:
  RSS is incomplete, but the complete article can
  be obtained from the accessible webpage.

FULL_CONTENT_UNAVAILABLE:
  The available RSS and webpage extraction methods
  have been tested, but full content cannot be
  obtained through permitted access.

INCONCLUSIVE:
  Insufficient evidence to establish completeness,
  such as temporary network failures, inaccessible
  reference content or ambiguous extraction results.

### Source-Level Classification

Aggregate article-level results.

- If all sufficiently tested articles are RSS_COMPLETE,
  classify the source as RSS_COMPLETE.

- If all sufficiently tested articles are complete
  through RSS or webpage extraction, and at least
  one requires a webpage fetch, classify the source
  as PAGE_FETCH_REQUIRED.

- If any article is FULL_CONTENT_UNAVAILABLE,
  report the source as MIXED, with the affected
  article counts and failure patterns.

- If evidence is insufficient, classify the source
  as INCONCLUSIVE.

Never label an entire source RSS_COMPLETE based on
a single article.

### Diagnostic Output

Provide a table showing:

- Article title
- RSS character count
- Webpage character count
- Completeness assessment
- Required extraction method
- Notes on limitations

Also provide a source summary:

- Number of articles tested
- RSS_COMPLETE count
- PAGE_FETCH_REQUIRED count
- FULL_CONTENT_UNAVAILABLE count
- INCONCLUSIVE count
- Recommended source-level extraction strategy
- Confidence and outstanding issues

### Efficiency Recommendation

Recommend the simplest reliable strategy:

1. Use RSS text directly where complete.
2. Fetch webpages only for incomplete RSS articles.
3. Use browser rendering only when necessary.
4. Flag articles without obtainable full content.
5. Avoid sending incomplete text to LLM scoring
   and summarisation without explicit handling.

Do not modify production fetchers without permission.

### Project context (aimobility_news)

- Feed URLs: `FEEDS`, `FEEDS_AI_CN` and `FEEDS_transport_CN` in
  `src/aimobility_news/config.py`; `feeds.known_feeds()` merges them.
- Existing read-only helpers in `src/aimobility_news/feeds.py` (no LLM calls):
  `inspect_feed_structure(source)` shows the raw RSS fields, and
  `inspect_extraction(sources, fetch_pages=True)` compares feed text with
  trafilatura page text. Reuse `http_get`, `html_to_text` and
  `fetch_page_text` rather than reimplementing them.
- Relevant settings: `PAGE_FETCH_SOURCES`, `FULL_TEXT_MIN_WORDS`,
  `MAX_CONTENT_WORDS`, `HTTP_TIMEOUT_OVERRIDES`. Measure length with
  `textlen.text_length` (English-word equivalents) as well as characters,
  since Chinese text has far fewer "words" per character.
- Run Python via the project venv as a module (relative imports), e.g.
  `.venv/Scripts/python -m aimobility_news.feeds`, and call
  `sys.stdout.reconfigure(encoding="utf-8")` before printing Chinese text.
- Playwright is installed in the venv; use it only for the step-5 checks.
- Put throwaway diagnostic scripts outside `src/` (or run them inline); the
  recommendation (e.g. adding a source to `PAGE_FETCH_SOURCES`) is for the
  user to approve.

---
name: build-slice
description: Build the next v0.6 web-interface slice in learning mode — concept briefing, user-chosen mode (watch / scaffold / drive), run and break it, review, learning log. Use when continuing v0.6 development.
---

The user is building v0.6 (`docs/v0.6-web-interface-spec.md`) partly to learn
Python and web development. They understand programming concepts but are
still developing Python proficiency. Working code is not enough: they should
understand it.

## Slice plan

| # | Slice (spec IDs) | Concepts |
|---|---|---|
| 0 | `queries.py` shared module; `reader.py` refactored onto it | sqlite3, parameterised SQL, row_factory, dataclasses, pytest fixtures |
| 1 | FastAPI hello, then today's briefing (A1) | routes, decorators, uvicorn, Jinja2, template inheritance |
| 2 | Article / story detail (A2) | path params, HTTPException, url_for |
| 3 | Archive and multi-day catch-up (B3, A3) | query params, type-hint validation, dates |
| 4 | FTS5 index and keyword search (B1) | virtual tables, MATCH, bm25, tokenizers (Chinese) |
| 5 | Facet filters (B2) | safe SQL from optional inputs, HTML forms |
| 6 | Near-misses and scoring explanations (D1, D2) | reusing ranking.py logic in the UI |
| 7 | Exit criterion (spec section 8) | TestClient tests, cleanup |

Progress is tracked in `docs/learning/progress.md` (create if missing):
which slices are done, the mode used, and where the current slice stopped.
Read it first to find the current slice and resume point.

## Rhythm for each slice

1. **Resume check.** Read `docs/learning/progress.md` and the relevant spec
   sections. Say which slice is next and what it delivers. Ask how much time
   the user has; size the session so it ends at a clean stopping point.
2. **Concept briefing** (short). The 2-3 new ideas, each with a tiny
   standalone example, not project code. Link to the project code they will
   touch.
3. **Ask for the mode** (AskUserQuestion):
   - **Watch:** Claude writes the code, explaining each part.
   - **Scaffold:** Claude writes the structure and leaves
     `# TODO (you): ...` gaps with a hint for the instructive parts (a
     query, a route body). The user fills them; Claude reviews.
   - **Drive:** the user writes it; Claude reviews and explains issues
     rather than silently fixing them.
   Suggested progression: Watch for slice 1, Scaffold from 2, Drive by 5-6.
4. **Build** in small steps. Keep code plain (explicit SQL, no ORM, no clever
   abstractions). Follow existing project style.
5. **Run it and break it.** Run the tests or the app; then try one bad input
   on purpose and read the traceback together.
6. **Recap.** Offer `/explain-code` on the main new file; suggest one optional
   micro-exercise (about 10 minutes) on real data.
7. **Learning log.** Prompt the user to write
   `docs/learning/slice-NN-<topic>.md` in their own words (concepts,
   pitfalls, how they would explain it). Check it for accuracy; do not write
   it for them.
8. **Update `docs/learning/progress.md`** with the stopping point, so the next
   session resumes cleanly.
9. **Commit** only when the user asks. The message should say what was
   learned as well as what changed.

## Rules

- Answer "why" questions with the reasoning, including the decisions
  recorded in the spec.
- Do not jump ahead to later slices or add features outside the spec.
- In Scaffold and Drive modes, do not fill in the user's TODOs unless asked.
- Do not touch `output/db/news.db` writes: v0.6 is read-only on it. Tests use
  a temporary database (see `tests/test_db.py`).

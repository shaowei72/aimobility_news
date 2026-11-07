# v0.6 learning progress

Slice plan and rhythm: `.claude/skills/build-slice/SKILL.md` (run `/build-slice`).

| Slice | Status | Mode | Notes |
|---|---|---|---|
| 0 — `web/queries.py` shared module | Committed 2026-11-07; learning log pending | Scaffold | 5 tests in `tests/test_queries.py` |
| 1 — FastAPI hello + briefing (A1) | — | | |
| 2 — Detail pages (A2) | — | | |
| 3 — Archive, catch-up (B3, A3) | — | | |
| 4 — FTS5 search (B1) | — | | |
| 5 — Facet filters (B2) | — | | |
| 6 — Near-misses, explanations (D1, D2) | — | | |
| 7 — Exit criterion | — | | |

## Resume point

Slice 0. The briefing covered: read-only connections and `sqlite3.Row`,
`?` placeholders vs f-strings in SQL, and splitting "load" (query) functions
from "render" (Markdown) functions.

**Scaffold written 2026-11-06** (uncommitted): `web/__init__.py`,
`web/queries.py` (TODO 1a-1e), TODO 2a-2b at the top of `reader.py`,
`tests/test_queries.py` (TODO 3a-3f; red until filled). Baseline reader
output saved in `output/slice0/before-all.md` and `before-its-all.md`
(`--since 2026-09-01 --until 2026-11-06`). **Next: the user fills the TODOs
in order 1 → 2 → 3, then Claude reviews.**

TODO 1 done and reviewed (2026-11-06). Learned: `parents[N]` counts from the
file's folder (fixed `[2]` → `[3]`); a `__main__` block calling an undefined
`main()` only fails when run; unused imports removed. Next: TODO 2 in
`reader.py`.

TODO 2 done and reviewed (2026-11-06). `reader.py` imports from
`.web.queries` (incl. `DEFAULT_DB`, so one definition); output identical to
the `output/slice0/before-*.md` baseline. Learned: `-m` sets `__package__`,
a direct-path run leaves it empty so relative imports fail; imports used
only in type hints still count as used. Next: TODO 3 in
`tests/test_queries.py`.

TODO 3a-3b done (2026-11-06). Fixture `its_db` builds 2 runs (`RUN1`,
`RUN2` constants), articles A/B/AIDB and 4 digest_items; 3b typed in from
Claude's code (user asked) but currently FAILS: the call is missing
`include_all=True` (TypeError: missing required argument). Fix that first. Learned: ERROR (fixture/setup broke) vs
FAILED (assert); a function without `return` returns None (why `add_run`
needs the ID in a variable first, while `add_article` returns the DB-made
id); reading a traceback up from the SQLite IntegrityError to the caller;
decorators (`@x` means `f = x(f)`); `db.session()` (creates schema,
migrates, commits) vs `connect_read_only()` (`mode=ro`, fails if missing);
list comprehensions. Optional: break 3b by flipping `ORDER BY d.run_id
DESC` to ASC, read the failure, undo.
**Resume: TODO 3c** (hint given: set comprehension of URLs), then 3d-3f,
then Slice 0 wrap-up (run-and-break, recap, learning log
`docs/learning/slice-00-queries.md`, commit if asked). Style nit pending:
spacing around `=`/commas in the fixture (maybe `ruff format`).

TODO 3b-3d done and reviewed (2026-11-07); 3 passed, 3e/3f still
placeholders. Learned: `TypeError` (wrong arguments: missing `include_all`)
vs `NameError` (`TRUE` instead of `True`); `sqlite3.Row` raises
`IndexError` for an unknown column (typo `degest_status`); a test that only
asserts absence passes on an empty result, so assert presence too (3c:
`urls == {A}`, proven by breaking `published = 1` → `= 2`); bracket shape
sets the type (`[...]` list, `{...}` set, a list never equals a string);
`!=` on sets vs `not in` for membership; copy-paste slip (`a1_rows`
asserted twice). `uv run pytest` runs the venv's launcher, same as
`uv run python -m pytest`. Did the break experiment (`DESC` → `ASC`, 3b
caught it). ruff is not installed (`uv add --dev ruff` if wanted).
**Resume: TODO 3e** (read-only connection: run the DELETE once without
`pytest.raises` to see the error type), then 3f, then Slice 0 wrap-up.

TODO 3e-3f done and reviewed (2026-11-07). Learned: `pytest.raises` (only
the failing line inside; `conn.close()` after the block), finding the
exception type from the traceback's last `E` line, `__mro__` and catching
specific vs broad types, `is None` vs `== None`, conditional expressions and
method chaining in `local_day`, flaky tests (an aware timestamp's day depends
on the machine's timezone; the user proved it by testing `+00:00`, which
gives `2026-11-04` on this machine).
Wrap-up done: full suite run; reader output differs from the `before-*.md`
baseline only because of a 2026-11-06 ~21:00 pipeline run (yesterday's
`after-*.md` matched exactly), so a before/after check needs frozen data;
bad `--since 2026-13-01` gives a clean argparse error. Scaffold `TODO (you)`
comments in the test file replaced with docstrings.
3f reverted to the naive string; full suite 47 passed. Slice 0 code
committed 2026-11-07.
**Resume (still Slice 0):** user writes `docs/learning/slice-00-queries.md`,
Claude checks it for accuracy. Then Slice 1 (FastAPI hello + briefing, A1).

Original plan:
1. Mode chosen: **Scaffold**. Claude sets up the module and leaves
   `# TODO (you):` gaps in the instructive parts (moving the load
   functions, the test fixture and assertions).
2. Create `src/aimobility_news/web/__init__.py` and `web/queries.py`
   (standard library only, read-only).
3. Move into it from `reader.py`: `connect_read_only`, `local_day`,
   `load_its_rows`, `load_episodes`, `story_urls`, `ai_score`, and the
   constants they use (`DEFAULT_DB`, `AIDB_SOURCE`).
   `render_*`, `*_entries`, argument parsing and `main()` stay in `reader.py`.
4. `reader.py` imports from `.web.queries`; the direct-path run form
   (`python src/.../reader.py`) is dropped (spec decision 5).
5. Check: `uv run python -m aimobility_news.reader` gives the same output as
   before (save a copy of the current output first to compare).
6. Tests: `tests/test_queries.py` with a temporary database, for
   `load_its_rows` (latest run wins) and `local_day`.

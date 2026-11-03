"""Split AI Daily Brief episodes into individual stories (v0.3 step 7).

Each episode is published as a Markdown digest (<edition_url>.md) and a
transcript (<edition_url>/transcript.md). In the digest, every `###` heading is
a talking point, not a story: one news story usually spans several headings,
and the main episode may be one essay or several separate topics. So:

1. Parse the `###` headings of the "Headlines" and "Main episode" sections
   (code).
2. Group each section's headings into stories (one LLM call per section, so
   headlines and main episode are never mixed).
3. Cut each story's part out of the transcript, from its first heading's minute
   to the end of its last heading's minute, plus a buffer at each end (code).
4. Summarise each story from its transcript excerpt, guided by its headings
   (one LLM call per story).
5. Save the headings, groups, excerpts and summaries per episode and model in
   the database (db.py, aidb_story_sets), so later runs and benchmarks reuse
   exactly the same output.
6. Optional (--compare): summarise the whole transcript in a single LLM call,
   then write a side-by-side report and ask a judge model to compare the two.

Outputs:
    <AIDB_DIR>/<date>/digest.md, transcript.md   source files (fetched once)
    database, aidb_story_sets                    steps 1-5, one row per episode and model
    <AIDB_DIR>/<date>/single-call__<model>.json  step 6, single-call summaries
    <AIDB_DIR>/<date>/compare__<model>.json/.md  step 6, judge verdict and report

Usage:
    uv run python -m aimobility_news.aidailybrief_transcript 2026-10-29 2026-10-30
    uv run python -m aimobility_news.aidailybrief_transcript --latest 3
    uv run python -m aimobility_news.aidailybrief_transcript --latest 3 --provider ollama  # local GPU; see docs/crash-investigation-2026-11-03.md
    uv run python -m aimobility_news.aidailybrief_transcript 2026-10-29 --compare

Saved results are reused; --refresh reruns the LLM steps.
"""

import argparse
import json
import random
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import requests
from pydantic import BaseModel, Field

from . import llm
from .config import AIDB_DIR, AIDB_BUFFER_BEFORE_MIN, AIDB_BUFFER_AFTER_MIN
from . import db
from .db import code_version


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "https://aidailybrief.ai/e"

# Digest sections whose `###` headings are stories; others ("By the numbers")
# are ignored
STORY_SECTIONS = ("headlines", "main episode")

# "### Title `[02:00]`" (minutes:seconds, or hours:minutes:seconds)
HEADING_RE = re.compile(r"^###\s+(.+?)\s*`\[(?:(\d+):)?(\d+):(\d+)\]`\s*$")
# Transcript markers, one per minute: "[00:02:00]"
MARKER_RE = re.compile(r"\[(\d{2}):(\d{2}):(\d{2})\]")


# ------------------------------------------------------------
# LLM output schemas
# ------------------------------------------------------------

class StoryGroup(BaseModel):
    title: str = Field(description="Short neutral title for the whole story")
    heading_ids: list[int] = Field(description="Ids of the headings in this story")


class StoryGrouping(BaseModel):
    stories: list[StoryGroup]


class StorySummary(BaseModel):
    headline: str = Field(description="Factual headline for the story")
    summary: str = Field(description="100-150 word summary of the story")
    key_points: list[str] = Field(description="3-6 key facts, figures or claims")


class EpisodeStories(BaseModel):
    stories: list[StorySummary]


class Verdict(BaseModel):
    coverage: int = Field(ge=1, le=5, description="Are all news stories in the transcript covered?")
    accuracy: int = Field(ge=1, le=5, description="Is everything stated supported by the transcript?")
    story_separation: int = Field(ge=1, le=5, description="One distinct story per entry, not merged or split?")
    specificity: int = Field(ge=1, le=5, description="Concrete names, figures and claims rather than generalities?")
    notes: str


class Comparison(BaseModel):
    version_a: Verdict
    version_b: Verdict
    preferred: Literal["A", "B", "tie"]
    reason: str


# ------------------------------------------------------------
# Step 0: fetch the episode (cached on disk)
# ------------------------------------------------------------

def episode_dir(date: str) -> Path:
    return PROJECT_ROOT / AIDB_DIR / date


def fetch_episode(date: str) -> tuple[str, str]:
    """Return (digest, transcript) Markdown, fetching only if not cached."""
    folder = episode_dir(date)
    folder.mkdir(parents=True, exist_ok=True)
    urls = {
        "digest": f"{BASE_URL}/{date}.md",
        "transcript": f"{BASE_URL}/{date}/transcript.md",
    }
    texts = {}
    for name, url in urls.items():
        path = folder / f"{name}.md"
        if not path.exists():
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            response.raise_for_status()
            path.write_text(response.text, encoding="utf-8")
        texts[name] = path.read_text(encoding="utf-8")
    return texts["digest"], texts["transcript"]


def latest_dates(n: int) -> list[str]:
    from .aidailybrief import fetch_aidailybrief_articles
    return [a.url.rsplit("/", 1)[-1] for a in fetch_aidailybrief_articles()[:n]]


# ------------------------------------------------------------
# Step 1: parse the digest headings
# ------------------------------------------------------------

@dataclass
class Heading:
    id: int
    section: str        # "headlines" or "main episode"
    title: str
    seconds: int        # position in the episode
    summary: str        # the digest's short paragraph under the heading
    url: str | None     # edition URL with the heading's #anchor


def parse_digest(digest: str) -> tuple[dict, list[Heading]]:
    """Return episode info (title, lead) and the story headings in order."""
    lines = digest.splitlines()
    episode = {"title": "", "lead": ""}

    # Title is the first "# " line; the lead is everything up to the first
    # "---" after the italic byline
    for line in lines:
        if line.startswith("# "):
            episode["title"] = line[2:].strip()
            break
    lead = []
    for line in lines[1:]:
        if line.strip() == "---" or line.startswith("## "):
            break
        if line.strip() and not line.startswith("*The AI Daily Brief"):
            lead.append(line.strip().strip("*"))
    episode["lead"] = "\n".join(lead)

    headings: list[Heading] = []
    section = None
    current = None
    body: list[str] = []

    def finish():
        if current is None:
            return
        summary = []
        for line in body:
            if line.startswith("Link:"):
                current.url = line.removeprefix("Link:").strip()
            elif line.startswith("*For:"):
                continue  # audience tag, not content
            elif line.strip():
                summary.append(line.strip())
        current.summary = " ".join(summary)
        headings.append(current)

    for line in lines:
        if line.startswith("## "):
            finish()
            current, body = None, []
            name = line[3:].strip().lower()
            section = name if name in STORY_SECTIONS else None
        elif line.startswith("### ") and section:
            finish()
            body = []
            match = HEADING_RE.match(line)
            if not match:
                print(f"WARNING: heading without timestamp skipped: {line[:80]}")
                current = None
                continue
            hours, minutes, secs = match.group(2, 3, 4)
            current = Heading(
                id=len(headings) + 1,
                section=section,
                title=match.group(1).strip(),
                seconds=int(hours or 0) * 3600 + int(minutes) * 60 + int(secs),
                summary="",
                url=None,
            )
        elif current is not None:
            body.append(line)
    finish()

    return episode, headings


def clock(seconds: int) -> str:
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


# ------------------------------------------------------------
# Step 2: group headings into stories (LLM, one call per section)
# ------------------------------------------------------------

def grouping_prompt(episode: dict, section: str, headings: list[Heading]) -> str:
    listing = "\n\n".join(
        f"[{h.id}] ({clock(h.seconds)}) {h.title}\n{h.summary}" for h in headings
    )
    if section == "headlines":
        context = (
            "These are the HEADLINES segment: a run of short news items. "
            "Several consecutive headings usually cover one news story "
            "(the announcement, a quote about it, figures, reactions)."
        )
    else:
        context = (
            "These are the MAIN EPISODE segment. It may be one single topic "
            "discussed from many angles (then return ONE story), or several "
            "separate topics in turn (then return one story per topic)."
        )

    return f"""
You are splitting a podcast episode summary into individual news stories.

Episode: {episode['title']}
{episode['lead']}

{context}

Each heading below is one talking point, with its id, its time in the
episode and a short summary.

Group the headings into distinct stories:
- A story is one event, announcement, company development or topic, together
  with the quotes, figures, commentary and reactions about it.
- A heading that is a quote or opinion belongs to the story it comments on.
- Headings appear in episode order and a story's headings are normally
  consecutive.
- Use every heading id exactly once.
- Do not split one story into several, and do not merge unrelated stories.
- Give each story a short, neutral, factual title.

Headings:

{listing}
""".strip()


def check_groups(groups: list[StoryGroup], ids: list[int]) -> tuple[list[StoryGroup], list[str]]:
    """Make every id appear exactly once; return fixed groups and warnings."""
    warnings = []
    valid = set(ids)
    seen = set()
    fixed = []
    for group in groups:
        kept = []
        for i in group.heading_ids:
            if i not in valid:
                warnings.append(f"unknown heading id {i} dropped")
            elif i in seen:
                warnings.append(f"heading {i} in more than one story; kept the first")
            else:
                kept.append(i)
                seen.add(i)
        if kept:
            fixed.append(StoryGroup(title=group.title, heading_ids=sorted(kept)))

    # A missing heading joins the story of the heading just before it
    for i in ids:
        if i in seen:
            continue
        warnings.append(f"heading {i} not grouped; added to the previous story")
        target = None
        for group in fixed:
            if any(j < i for j in group.heading_ids):
                target = group
        if target is None and fixed:
            target = fixed[0]
        if target is None:
            fixed.append(StoryGroup(title="(ungrouped)", heading_ids=[i]))
        else:
            target.heading_ids = sorted(target.heading_ids + [i])
        seen.add(i)

    fixed.sort(key=lambda g: g.heading_ids[0])

    for group in fixed:
        span = group.heading_ids
        if span != list(range(span[0], span[-1] + 1)):
            warnings.append(f"story {group.title!r} has non-consecutive headings {span}")

    return fixed, warnings


# ------------------------------------------------------------
# Step 3: cut the transcript
# ------------------------------------------------------------

def transcript_markers(transcript: str) -> list[tuple[int, int]]:
    """(seconds, character position) of each minute marker."""
    return [
        (int(h) * 3600 + int(m) * 60 + int(s), match.start())
        for match in MARKER_RE.finditer(transcript)
        for h, m, s in [match.groups()]
    ]


def cut_transcript(transcript: str, markers: list[tuple[int, int]], start: int, end: int) -> str:
    """Text between the markers at `start` and `end` seconds, markers removed."""
    if not markers:
        return ""
    start_pos = next((pos for secs, pos in markers if secs >= start), len(transcript))
    end_pos = next((pos for secs, pos in markers if secs >= end), len(transcript))
    text = MARKER_RE.sub(" ", transcript[start_pos:end_pos])
    return re.sub(r"\s+", " ", text).strip()


def story_window(headings: list[Heading]) -> tuple[int, int]:
    # A heading's minute says the story is somewhere in that minute, so the
    # story runs to the end of the last heading's minute; then add buffers.
    start = min(h.seconds for h in headings) - AIDB_BUFFER_BEFORE_MIN * 60
    end = max(h.seconds for h in headings) + 60 + AIDB_BUFFER_AFTER_MIN * 60
    return max(start, 0), end


# ------------------------------------------------------------
# Step 4: summarise each story (LLM, one call per story)
# ------------------------------------------------------------

def story_prompt(
    episode: dict, title: str, headings: list[Heading], excerpt: str, neighbours: list[str]
) -> str:
    outline = "\n".join(f"- {h.title}: {h.summary}" for h in headings)
    others = "\n".join(f"- {t}" for t in neighbours) or "- (none)"
    return f"""
Summarise one news story from a podcast transcript.

Podcast: The AI Daily Brief, episode "{episode['title']}"
Story: {title}

The story's talking points, from the episode's published summary:
{outline}

Transcript excerpt (spoken, lightly punctuated). It was cut by the minute,
so it may start or end with part of a neighbouring story, and it may contain
sponsor messages. Ignore anything not about this story, in particular these
neighbouring stories, which are summarised separately:
{others}

{excerpt}

Write:
- headline: a factual headline for this story
- summary: 100-150 words covering what happened, who is involved, the key
  figures, and the host's main point or analysis (attribute opinions)
- key_points: 3-6 concrete facts, figures or claims

Use only information in the excerpt and the talking points above; do not add
outside knowledge.
""".strip()


# ------------------------------------------------------------
# Steps 1-5: build and save the stories for one episode
# ------------------------------------------------------------

def model_tag(task: str) -> str:
    # "openai:gpt-6.1-sol" -> "openai_gpt-6.1-sol", safe as a file name
    return re.sub(r"[^A-Za-z0-9._-]+", "_", llm.describe(task).replace(":", "_", 1))


def run_info(task: str) -> dict:
    return {
        "run_id": llm.RUN_ID,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code_version": code_version(),
        "model": llm.describe(task),
    }


def build_stories(date: str, refresh: bool = False) -> dict:
    model = llm.describe("transcript")
    if not refresh:
        with db.session() as conn:
            saved = db.load_story_set(conn, date, model)
        if saved:
            print(f"  reusing stories for {date} ({model}) from the database")
            return saved

    digest, transcript = fetch_episode(date)
    episode, headings = parse_digest(digest)
    markers = transcript_markers(transcript)
    by_id = {h.id: h for h in headings}

    result = {
        **run_info("transcript"),
        "date": date,
        "url": f"{BASE_URL}/{date}",
        "episode_title": episode["title"],
        "episode_lead": episode["lead"],
        "buffer_minutes": [AIDB_BUFFER_BEFORE_MIN, AIDB_BUFFER_AFTER_MIN],
        "transcript_words": len(MARKER_RE.sub(" ", transcript).split()),
        "headings": [asdict(h) for h in headings],
        "groupings": [],
        "stories": [],
    }

    for section in STORY_SECTIONS:
        section_headings = [h for h in headings if h.section == section]
        if not section_headings:
            continue

        # Step 2
        grouping = llm.parse(
            grouping_prompt(episode, section, section_headings),
            StoryGrouping,
            task="transcript",
            label=f"AIDB {date} group {section}",
        )
        groups, warnings = check_groups(grouping.stories, [h.id for h in section_headings])
        for w in warnings:
            print(f"  WARNING ({section}): {w}")
        result["groupings"].append({
            "section": section,
            "raw": grouping.model_dump(),
            "warnings": warnings,
        })

        for n, group in enumerate(groups, 1):
            neighbours = [g.title for g in groups[max(n - 2, 0):n + 1] if g is not group]
            story_headings = [by_id[i] for i in group.heading_ids]

            # Step 3
            start, end = story_window(story_headings)
            excerpt = cut_transcript(transcript, markers, start, end)

            story = {
                "id": f"{section.replace(' ', '-')}-{n}",
                "section": section,
                "title": group.title,
                "heading_ids": group.heading_ids,
                "url": story_headings[0].url or result["url"],
                "window": {"start": clock(start), "end": clock(end)},
                "excerpt_words": len(excerpt.split()),
                "excerpt": excerpt,
                "summary": None,
                "summary_error": None,
            }

            # Step 4
            try:
                summary = llm.parse(
                    story_prompt(episode, group.title, story_headings, excerpt, neighbours),
                    StorySummary,
                    task="transcript",
                    label=f"AIDB {date} {group.title}",
                )
                story["summary"] = summary.model_dump()
            except Exception as e:
                story["summary_error"] = f"{type(e).__name__}: {e}"
                print(f"  WARNING: summary failed for {group.title!r}: {e}")

            result["stories"].append(story)

    # Step 5
    with db.session() as conn:
        db.save_story_set(conn, result)
    print(f"  saved stories for {date} ({model}) to the database")
    return result


# ------------------------------------------------------------
# Step 6 (optional): single-call baseline and comparison
# ------------------------------------------------------------

def single_call_prompt(transcript_text: str) -> str:
    return f"""
Below is the full transcript of one episode of The AI Daily Brief podcast.
Typically it has a headlines segment of short news items, then a main episode
on one or more topics. Ignore sponsor messages and housekeeping.

Identify every distinct news story or topic and summarise each:
- headline: a factual headline
- summary: 100-150 words covering what happened, who is involved, the key
  figures, and the host's main point or analysis (attribute opinions)
- key_points: 3-6 concrete facts, figures or claims

A story is one event, announcement, company development or topic, together
with the quotes, figures and commentary about it. Do not split one story into
several or merge unrelated stories. Use only information in the transcript.

Transcript:

{transcript_text}
""".strip()


def build_single_call(date: str, refresh: bool = False) -> dict:
    out_path = episode_dir(date) / f"single-call__{model_tag('transcript')}.json"
    if out_path.exists() and not refresh:
        print(f"  reusing {out_path.relative_to(PROJECT_ROOT)}")
        return json.loads(out_path.read_text(encoding="utf-8"))

    _, transcript = fetch_episode(date)
    text = re.sub(r"\s+", " ", MARKER_RE.sub(" ", transcript)).strip()
    stories = llm.parse(
        single_call_prompt(text),
        EpisodeStories,
        task="transcript",
        label=f"AIDB {date} single call",
    )
    result = {**run_info("transcript"), "date": date, **stories.model_dump()}
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  saved {out_path.relative_to(PROJECT_ROOT)}")
    return result


def format_stories(stories: list[dict]) -> str:
    blocks = []
    for n, s in enumerate(stories, 1):
        points = "\n".join(f"  - {p}" for p in s["key_points"])
        blocks.append(f"{n}. {s['headline']}\n{s['summary']}\n{points}")
    return "\n\n".join(blocks)


def judge_prompt(transcript_text: str, version_a: str, version_b: str) -> str:
    return f"""
You are evaluating two sets of story summaries of the same podcast episode
against its transcript. Score each version from 1 (poor) to 5 (excellent) on:
- coverage: every news story in the transcript is covered
- accuracy: everything stated is supported by the transcript
- story_separation: one distinct story per entry, not merged or split
- specificity: concrete names, figures and claims rather than generalities

Then say which version is better overall (A, B or tie) and why. Judge only
quality, not length or order.

Transcript:

{transcript_text}

=== VERSION A ===

{version_a}

=== VERSION B ===

{version_b}
""".strip()


def compare(date: str, judge_provider: str | None, refresh: bool = False) -> None:
    pipeline = build_stories(date, refresh)
    single = build_single_call(date, refresh)

    tag = model_tag("transcript")
    json_path = episode_dir(date) / f"compare__{tag}.json"
    md_path = episode_dir(date) / f"compare__{tag}.md"

    pipeline_stories = [s["summary"] for s in pipeline["stories"] if s["summary"]]
    single_stories = single["stories"]

    verdict = None
    if json_path.exists() and not refresh:
        verdict = json.loads(json_path.read_text(encoding="utf-8"))
        print(f"  reusing {json_path.relative_to(PROJECT_ROOT)}")
    else:
        _, transcript = fetch_episode(date)
        text = re.sub(r"\s+", " ", MARKER_RE.sub(" ", transcript)).strip()

        # Random A/B order, so a judge's position bias does not favour one
        pipeline_is_a = random.random() < 0.5
        a, b = (pipeline_stories, single_stories) if pipeline_is_a else (single_stories, pipeline_stories)
        try:
            result = llm.parse(
                judge_prompt(text, format_stories(a), format_stories(b)),
                Comparison,
                task="judge",
                provider=judge_provider,
                label=f"AIDB {date} judge",
            )
            names = {"A": "pipeline" if pipeline_is_a else "single_call",
                     "B": "single_call" if pipeline_is_a else "pipeline"}
            verdict = {
                "run_id": llm.RUN_ID,
                "judge": llm.describe("judge", judge_provider),
                "summaries_by": llm.describe("transcript"),
                "pipeline": (result.version_a if pipeline_is_a else result.version_b).model_dump(),
                "single_call": (result.version_b if pipeline_is_a else result.version_a).model_dump(),
                "preferred": names.get(result.preferred, "tie"),
                "reason": result.reason,
                "pipeline_was": "A" if pipeline_is_a else "B",
            }
            json_path.write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"  WARNING: judge call failed: {e}")

    # Side-by-side report for manual review
    lines = [
        f"# AI Daily Brief {date}: pipeline vs single call",
        "",
        f"Episode: {pipeline['episode_title']}  ",
        f"Summaries by: {pipeline['model']}",
        "",
    ]
    if verdict:
        lines += [
            f"## Judge ({verdict['judge']})",
            "",
            "| | coverage | accuracy | story separation | specificity |",
            "|---|---|---|---|---|",
        ]
        for name in ("pipeline", "single_call"):
            v = verdict[name]
            lines.append(f"| {name} | {v['coverage']} | {v['accuracy']} | {v['story_separation']} | {v['specificity']} |")
        lines += [
            "",
            f"**Preferred:** {verdict['preferred']}. {verdict['reason']}",
            "",
            f"- pipeline: {verdict['pipeline']['notes']}",
            f"- single_call: {verdict['single_call']['notes']}",
            "",
        ]
    lines += [f"## Pipeline ({len(pipeline_stories)} stories)", ""]
    for s in pipeline["stories"]:
        lines.append(f"### [{s['section']}] {s['title']}")
        lines.append(f"*Headings {s['heading_ids']}, transcript {s['window']['start']}-{s['window']['end']}, {s['excerpt_words']} words*")
        lines.append("")
        if s["summary"]:
            lines.append(f"**{s['summary']['headline']}**")
            lines.append("")
            lines.append(s["summary"]["summary"])
            lines += [f"- {p}" for p in s["summary"]["key_points"]]
        else:
            lines.append(f"Summary failed: {s['summary_error']}")
        lines.append("")
    lines += [f"## Single call ({len(single_stories)} stories)", ""]
    for s in single_stories:
        lines += [f"### {s['headline']}", "", s["summary"]]
        lines += [f"- {p}" for p in s["key_points"]]
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  saved {md_path.relative_to(PROJECT_ROOT)}")


# ------------------------------------------------------------
# Command line
# ------------------------------------------------------------

def print_stories(result: dict) -> None:
    print(f"  {result['episode_title']} ({len(result['headings'])} headings -> {len(result['stories'])} stories)")
    for s in result["stories"]:
        status = "" if s["summary"] else "  [SUMMARY FAILED]"
        print(
            f"    {s['id']:<16} {s['window']['start'][3:]}-{s['window']['end'][3:]} "
            f"{s['excerpt_words']:>5} words  headings {s['heading_ids']}  {s['title']}{status}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Split AI Daily Brief episodes into stories")
    parser.add_argument("dates", nargs="*", help="episode dates, YYYY-MM-DD")
    parser.add_argument("--latest", type=int, default=0, help="also process the latest N episodes")
    parser.add_argument("--provider", choices=llm.PROVIDERS, help="LLM provider for grouping and summaries")
    parser.add_argument("--compare", action="store_true", help="step 6: compare with a single-call summary")
    parser.add_argument("--judge-provider", choices=llm.PROVIDERS, default="openai",
                        help="provider for the comparison judge (default openai)")
    parser.add_argument("--refresh", action="store_true", help="rerun LLM steps even if saved")
    args = parser.parse_args()

    if args.provider:
        llm.set_provider(args.provider)

    dates = list(args.dates)
    if args.latest:
        dates += [d for d in latest_dates(args.latest) if d not in dates]
    if not dates:
        dates = latest_dates(1)

    print(f"Grouping and summaries: {llm.describe('transcript')}")
    for date in dates:
        print(f"\n{date}")
        try:
            print_stories(build_stories(date, args.refresh))
            if args.compare:
                compare(date, args.judge_provider, args.refresh)
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()

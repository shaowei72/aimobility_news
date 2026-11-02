"""Provider switch for LLM calls.

Scoring and digest code call parse() with a prompt, a Pydantic schema and a
task name ("scoring" or "digest"). The provider (OpenAI or Ollama) and the
model per task come from config.py, and main.py can override the provider
for a run with --provider.

Prompts stay in scoring.py and digest.py, so both providers always get
exactly the same prompt.
"""

import csv
import time
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .config import LLM_PROVIDER, LLM_MODELS, LLM_CALL_LOG, OLLAMA_NUM_CTX


T = TypeVar("T", bound=BaseModel)

PROVIDERS = ("openai", "ollama")

_provider = LLM_PROVIDER

# Identifies one pipeline run in the call log (set when the process starts)
RUN_ID = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOG_FIELDS = [
    "run_id", "timestamp", "provider", "model", "task", "label", "status",
    "attempts", "prompt_tokens", "output_tokens", "num_ctx", "seconds",
]


def set_provider(name: str) -> None:
    global _provider
    if name not in PROVIDERS:
        raise ValueError(f"Unknown LLM provider {name!r}; use one of {PROVIDERS}")
    _provider = name


def get_provider() -> str:
    return _provider


def model_for(task: str, provider: str | None = None) -> str:
    return LLM_MODELS[provider or _provider][task]


def describe(task: str, provider: str | None = None) -> str:
    # e.g. "ollama:qwen3.5:9b", for logs and the debug digest
    provider = provider or _provider
    return f"{provider}:{model_for(task, provider)}"


def parse(
    prompt: str,
    schema: type[T],
    task: str,
    provider: str | None = None,
    label: str = "",
) -> T:
    """Run one structured LLM call. `label` (e.g. the article title) is
    only written to the call log."""
    provider = provider or _provider
    model = model_for(task, provider)

    # Imported here so a run only loads (and needs credentials for) the
    # provider it actually uses.
    if provider == "openai":
        from . import llm_openai as backend
    elif provider == "ollama":
        from . import llm_ollama as backend
    else:
        raise ValueError(f"Unknown LLM provider {provider!r}; use one of {PROVIDERS}")

    backend.last_call_stats.clear()
    status = "error"
    start = time.perf_counter()
    try:
        result = backend.parse(prompt, schema, model)
        status = "ok"
        return result
    finally:
        stats = backend.last_call_stats
        log_call({
            "run_id": RUN_ID,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "provider": provider,
            "model": model,
            "task": task,
            "label": label,
            "status": status,
            "attempts": stats.get("attempt"),
            "prompt_tokens": stats.get("prompt_tokens"),
            "output_tokens": stats.get("output_tokens"),
            "num_ctx": OLLAMA_NUM_CTX if provider == "ollama" else "",
            # Wall-clock time for the whole call, including retries
            "seconds": round(time.perf_counter() - start, 2),
        })


def log_call(row: dict) -> None:
    if not LLM_CALL_LOG:
        return

    path = PROJECT_ROOT / LLM_CALL_LOG
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
            if new_file:
                writer.writeheader()
            writer.writerow(row)
    except OSError as e:
        # e.g. the CSV is open in Excel; never let logging stop a run
        print(f"WARNING: could not write LLM call log {path}: {e}")

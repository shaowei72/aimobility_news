"""Provider switch for LLM calls.

Scoring and digest code call parse() with a prompt, a Pydantic schema and a
task name ("scoring" or "digest"). The provider (OpenAI or Ollama) and the
model per task come from config.py, and main.py can override the provider
for a run with --provider.

Prompts stay in scoring.py and digest.py, so both providers always get
exactly the same prompt.
"""

from typing import TypeVar

from pydantic import BaseModel

from .config import LLM_PROVIDER, LLM_MODELS


T = TypeVar("T", bound=BaseModel)

PROVIDERS = ("openai", "ollama")

_provider = LLM_PROVIDER


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
) -> T:
    provider = provider or _provider
    model = model_for(task, provider)

    # Imported here so a run only loads (and needs credentials for) the
    # provider it actually uses.
    if provider == "openai":
        from . import llm_openai
        return llm_openai.parse(prompt, schema, model)

    if provider == "ollama":
        from . import llm_ollama
        return llm_ollama.parse(prompt, schema, model)

    raise ValueError(f"Unknown LLM provider {provider!r}; use one of {PROVIDERS}")

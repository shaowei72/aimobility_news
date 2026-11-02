"""Ollama provider: local models via the native /api/chat endpoint.

The Pydantic schema is passed as `format`, so Ollama constrains the output
to that JSON schema. The context window (num_ctx) is set explicitly: if the
prompt is longer than the context, Ollama truncates it without an error and
the model answers from partial input.
"""

from typing import TypeVar

import requests
from pydantic import BaseModel, ValidationError

from .config import (
    OLLAMA_HOST,
    OLLAMA_NUM_CTX,
    OLLAMA_TEMPERATURE,
    OLLAMA_THINK,
    OLLAMA_TIMEOUT,
    OLLAMA_MAX_ATTEMPTS,
)


T = TypeVar("T", bound=BaseModel)

# Token counts and timing of the most recent call, for benchmarking
last_call_stats: dict = {}


def chat(prompt: str, schema: type[BaseModel], model: str) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "format": schema.model_json_schema(),
        "stream": False,
        "options": {
            "temperature": OLLAMA_TEMPERATURE,
            "num_ctx": OLLAMA_NUM_CTX,
        },
    }
    if OLLAMA_THINK is not None:
        payload["think"] = OLLAMA_THINK

    response = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json=payload,
        timeout=OLLAMA_TIMEOUT,
    )

    if not response.ok:
        raise RuntimeError(
            f"Ollama returned HTTP {response.status_code} for model "
            f"{model!r}: {response.text[:300]}"
        )

    return response.json()


def parse(prompt: str, schema: type[T], model: str) -> T:
    last_error: Exception | None = None

    for attempt in range(1, OLLAMA_MAX_ATTEMPTS + 1):
        data = chat(prompt, schema, model)

        prompt_tokens = data.get("prompt_eval_count") or 0
        last_call_stats.clear()
        last_call_stats.update(
            model=model,
            attempt=attempt,
            prompt_tokens=prompt_tokens,
            output_tokens=data.get("eval_count") or 0,
            seconds=(data.get("total_duration") or 0) / 1e9,
        )

        # A prompt that fills the whole context was almost certainly cut off
        if prompt_tokens >= OLLAMA_NUM_CTX:
            print(
                f"WARNING: prompt used {prompt_tokens} tokens, the full "
                f"OLLAMA_NUM_CTX ({OLLAMA_NUM_CTX}); input was probably "
                f"truncated. Increase OLLAMA_NUM_CTX."
            )

        content = data.get("message", {}).get("content", "")

        try:
            return schema.model_validate_json(content)
        except ValidationError as e:
            last_error = e
            print(
                f"WARNING: invalid {schema.__name__} from {model} "
                f"(attempt {attempt}/{OLLAMA_MAX_ATTEMPTS}): {content[:200]!r}"
            )

    raise RuntimeError(
        f"{model} did not return a valid {schema.__name__} after "
        f"{OLLAMA_MAX_ATTEMPTS} attempts"
    ) from last_error

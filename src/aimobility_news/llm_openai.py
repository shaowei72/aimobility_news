"""OpenAI provider: structured output via the Responses API."""

from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)

_client: OpenAI | None = None


def get_client() -> OpenAI:
    # Created on first use, so importing this module needs no API key
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def parse(prompt: str, schema: type[T], model: str) -> T:
    response = get_client().responses.parse(
        model=model,
        input=prompt,
        text_format=schema,
    )
    return response.output_parsed

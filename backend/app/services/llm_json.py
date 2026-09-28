"""
Structured (JSON-mode) Gemini calls for the agent's small decision steps (Phase 4).

Uses the Gemini SDK directly rather than a LangChain chat model: inside the graph, LangChain models emit
``on_chat_model_stream`` events, which would leak decision JSON into the user-facing answer stream.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pydantic import BaseModel

from app.services.metrics import record_sdk_usage

T = TypeVar("T", bound=BaseModel)

# An injectable structured-output call: (prompt, schema) -> validated instance. Steps take one of these so
# they can be unit-tested with a stub and no network.
StructuredLLM = Callable[[str, type[T]], Awaitable[T]]


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    return text


def gemini_structured_llm(model: str, api_key: str, max_output_tokens: int) -> StructuredLLM:
    """A StructuredLLM backed by Gemini JSON mode (temperature 0). Raises on invalid output."""

    def call(prompt: str) -> str:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        response = genai.GenerativeModel(model).generate_content(
            prompt,
            generation_config={
                "temperature": 0,
                "max_output_tokens": max_output_tokens,
                "response_mime_type": "application/json",
            },
        )
        record_sdk_usage(model, "agent", response)
        return response.text

    async def llm(prompt: str, schema: type[T]) -> T:
        raw = await asyncio.to_thread(call, prompt)
        return schema.model_validate_json(_strip_fences(raw))

    return llm

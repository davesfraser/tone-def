from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from typing import Any, cast

import instructor
import litellm
from pydantic import BaseModel
from tenacity import AsyncRetrying, Retrying, stop_after_attempt, wait_exponential

from tonedef.cache import (
    completion_cache_key,
    read_cached_completion,
    read_cached_json,
    write_cached_completion,
    write_cached_json,
)
from tonedef.settings import settings
from tonedef.tracing import trace_llm_call

Message = Mapping[str, str]


def _retrying() -> Retrying:
    return Retrying(
        stop=stop_after_attempt(settings.retry_max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )


def _async_retrying() -> AsyncRetrying:
    return AsyncRetrying(
        stop=stop_after_attempt(settings.retry_max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )


@lru_cache(maxsize=1)
def _instructor_client() -> Any:
    return instructor.from_litellm(litellm.completion)


@lru_cache(maxsize=1)
def _async_instructor_client() -> Any:
    return instructor.from_litellm(litellm.acompletion)


def _message_content(response: Any) -> str:
    content = response.choices[0].message.content
    if not isinstance(content, str):
        msg = "LLM response did not contain text content"
        raise TypeError(msg)
    return content


def _completion_payload(
    messages: list[Message],
    *,
    model: str,
    max_tokens: int,
    temperature: float,
    extra: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "extra": dict(extra),
    }


def _schema_payload(schema: type[BaseModel]) -> dict[str, Any]:
    return {
        "name": f"{schema.__module__}.{schema.__qualname__}",
        "json_schema": schema.model_json_schema(),
    }


def complete(
    messages: list[Message],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    **kwargs: Any,
) -> str:
    """Return a plain text completion through LiteLLM."""
    for attempt in _retrying():
        with attempt:
            return _complete_once(
                messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )

    msg = "Retrying stopped without returning a completion"
    raise RuntimeError(msg)


def _complete_once(
    messages: list[Message],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    **kwargs: Any,
) -> str:
    resolved_model = model or settings.default_model
    resolved_max_tokens = max_tokens or settings.max_tokens
    resolved_temperature = settings.temperature if temperature is None else temperature
    payload = _completion_payload(
        messages,
        model=resolved_model,
        max_tokens=resolved_max_tokens,
        temperature=resolved_temperature,
        extra=kwargs,
    )
    cache_key = completion_cache_key(payload)
    cached = read_cached_completion(cache_key)
    if cached is not None:
        return cached

    with trace_llm_call("llm.complete", payload):
        response = litellm.completion(
            model=resolved_model,
            messages=messages,
            max_tokens=resolved_max_tokens,
            temperature=resolved_temperature,
            timeout=settings.request_timeout_seconds,
            **kwargs,
        )

    content = _message_content(response)
    write_cached_completion(cache_key, content)
    return content


async def acomplete(
    messages: list[Message],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    **kwargs: Any,
) -> str:
    """Return a plain text completion through LiteLLM's async API."""
    async for attempt in _async_retrying():
        with attempt:
            return await _acomplete_once(
                messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )

    msg = "Retrying stopped without returning a completion"
    raise RuntimeError(msg)


async def _acomplete_once(
    messages: list[Message],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    **kwargs: Any,
) -> str:
    resolved_model = model or settings.default_model
    resolved_max_tokens = max_tokens or settings.max_tokens
    resolved_temperature = settings.temperature if temperature is None else temperature
    payload = _completion_payload(
        messages,
        model=resolved_model,
        max_tokens=resolved_max_tokens,
        temperature=resolved_temperature,
        extra=kwargs,
    )
    cache_key = completion_cache_key(payload)
    cached = read_cached_completion(cache_key)
    if cached is not None:
        return cached

    with trace_llm_call("llm.acomplete", payload):
        response = await litellm.acompletion(
            model=resolved_model,
            messages=messages,
            max_tokens=resolved_max_tokens,
            temperature=resolved_temperature,
            timeout=settings.request_timeout_seconds,
            **kwargs,
        )

    content = _message_content(response)
    write_cached_completion(cache_key, content)
    return content


def complete_structured[T: BaseModel](
    messages: list[Message],
    schema: type[T],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    **kwargs: Any,
) -> T:
    """Return a validated Pydantic object through Instructor."""
    resolved_model = model or settings.default_model
    resolved_max_tokens = max_tokens or settings.max_tokens
    resolved_temperature = settings.temperature if temperature is None else temperature
    payload = _completion_payload(
        messages,
        model=resolved_model,
        max_tokens=resolved_max_tokens,
        temperature=resolved_temperature,
        extra={
            "schema": _schema_payload(schema),
            **kwargs,
        },
    )
    cache_key = completion_cache_key(payload)
    cached = read_cached_json(cache_key)
    if cached is not None:
        return schema.model_validate_json(cached)

    response = _instructor_client().chat.completions.create(
        model=resolved_model,
        messages=messages,
        response_model=schema,
        max_tokens=resolved_max_tokens,
        temperature=resolved_temperature,
        max_retries=settings.retry_max_attempts,
        **kwargs,
    )
    result = cast(T, response)
    write_cached_json(cache_key, result.model_dump_json())
    return result


async def acomplete_structured[T: BaseModel](
    messages: list[Message],
    schema: type[T],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    **kwargs: Any,
) -> T:
    """Return a validated Pydantic object through Instructor's async path."""
    resolved_model = model or settings.default_model
    resolved_max_tokens = max_tokens or settings.max_tokens
    resolved_temperature = settings.temperature if temperature is None else temperature
    payload = _completion_payload(
        messages,
        model=resolved_model,
        max_tokens=resolved_max_tokens,
        temperature=resolved_temperature,
        extra={
            "schema": _schema_payload(schema),
            **kwargs,
        },
    )
    cache_key = completion_cache_key(payload)
    cached = read_cached_json(cache_key)
    if cached is not None:
        return schema.model_validate_json(cached)

    response = await _async_instructor_client().chat.completions.create(
        model=resolved_model,
        messages=messages,
        response_model=schema,
        max_tokens=resolved_max_tokens,
        temperature=resolved_temperature,
        max_retries=settings.retry_max_attempts,
        **kwargs,
    )
    result = cast(T, response)
    write_cached_json(cache_key, result.model_dump_json())
    return result

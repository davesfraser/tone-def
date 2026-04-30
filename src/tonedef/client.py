from __future__ import annotations

import logging
import time
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
from tonedef.llm_usage import LLMUsageRecord, record_llm_usage
from tonedef.settings import settings
from tonedef.tracing import trace_llm_call

Message = Mapping[str, str]
_log = logging.getLogger(__name__)


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


def _trace_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return non-content request metadata suitable for traces/logs."""
    extra = payload.get("extra", {})
    return {
        "model": payload.get("model"),
        "max_tokens": payload.get("max_tokens"),
        "temperature": payload.get("temperature"),
        "extra_keys": sorted(extra) if isinstance(extra, dict) else [],
    }


def _schema_payload(schema: type[BaseModel]) -> dict[str, Any]:
    return {
        "name": f"{schema.__module__}.{schema.__qualname__}",
        "json_schema": schema.model_json_schema(),
    }


def _usage_value(usage: Any, key: str) -> int | None:
    if usage is None:
        return None
    value = usage.get(key) if isinstance(usage, dict) else getattr(usage, key, None)
    return value if isinstance(value, int) else None


def _response_usage(response: Any) -> tuple[int | None, int | None, int | None]:
    usage = getattr(response, "usage", None)
    return (
        _usage_value(usage, "prompt_tokens"),
        _usage_value(usage, "completion_tokens"),
        _usage_value(usage, "total_tokens"),
    )


def _response_cost(response: Any) -> float | None:
    hidden = getattr(response, "_hidden_params", None)
    if isinstance(hidden, dict):
        cost = hidden.get("response_cost")
        if isinstance(cost, (int, float)):
            return float(cost)

    completion_cost = getattr(litellm, "completion_cost", None)
    if completion_cost is None:
        return None
    try:
        cost = completion_cost(completion_response=response)
    except Exception:
        return None
    return float(cost) if isinstance(cost, (int, float)) else None


def _record_usage(
    *,
    operation: str,
    model: str,
    latency_seconds: float,
    cache_hit: bool = False,
    response: Any | None = None,
    error: Exception | None = None,
) -> None:
    prompt_tokens, completion_tokens, total_tokens = _response_usage(response)
    estimated_cost = 0.0 if cache_hit else _response_cost(response)
    error_name = type(error).__name__ if error is not None else None
    record = LLMUsageRecord(
        operation=operation,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost,
        latency_seconds=latency_seconds,
        cache_hit=cache_hit,
        error=error_name,
    )
    record_llm_usage(record)
    _log.info(
        "%s model=%s cache_hit=%s latency_seconds=%.3f prompt_tokens=%s "
        "completion_tokens=%s total_tokens=%s estimated_cost_usd=%s error=%s",
        operation,
        model,
        cache_hit,
        latency_seconds,
        prompt_tokens,
        completion_tokens,
        total_tokens,
        estimated_cost,
        error_name,
    )


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
        _record_usage(
            operation="llm.complete",
            model=resolved_model,
            latency_seconds=0.0,
            cache_hit=True,
        )
        return cached

    start = time.perf_counter()
    try:
        with trace_llm_call("llm.complete", _trace_payload(payload)):
            response = litellm.completion(
                model=resolved_model,
                messages=messages,
                max_tokens=resolved_max_tokens,
                temperature=resolved_temperature,
                timeout=settings.request_timeout_seconds,
                **kwargs,
            )
    except Exception as exc:
        _record_usage(
            operation="llm.complete",
            model=resolved_model,
            latency_seconds=time.perf_counter() - start,
            error=exc,
        )
        raise

    _record_usage(
        operation="llm.complete",
        model=resolved_model,
        latency_seconds=time.perf_counter() - start,
        response=response,
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
        _record_usage(
            operation="llm.acomplete",
            model=resolved_model,
            latency_seconds=0.0,
            cache_hit=True,
        )
        return cached

    start = time.perf_counter()
    try:
        with trace_llm_call("llm.acomplete", _trace_payload(payload)):
            response = await litellm.acompletion(
                model=resolved_model,
                messages=messages,
                max_tokens=resolved_max_tokens,
                temperature=resolved_temperature,
                timeout=settings.request_timeout_seconds,
                **kwargs,
            )
    except Exception as exc:
        _record_usage(
            operation="llm.acomplete",
            model=resolved_model,
            latency_seconds=time.perf_counter() - start,
            error=exc,
        )
        raise

    _record_usage(
        operation="llm.acomplete",
        model=resolved_model,
        latency_seconds=time.perf_counter() - start,
        response=response,
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
        _record_usage(
            operation="llm.complete_structured",
            model=resolved_model,
            latency_seconds=0.0,
            cache_hit=True,
        )
        return schema.model_validate_json(cached)

    start = time.perf_counter()
    try:
        response = _instructor_client().chat.completions.create(
            model=resolved_model,
            messages=messages,
            response_model=schema,
            max_tokens=resolved_max_tokens,
            temperature=resolved_temperature,
            max_retries=settings.retry_max_attempts,
            **kwargs,
        )
    except Exception as exc:
        _record_usage(
            operation="llm.complete_structured",
            model=resolved_model,
            latency_seconds=time.perf_counter() - start,
            error=exc,
        )
        raise

    _record_usage(
        operation="llm.complete_structured",
        model=resolved_model,
        latency_seconds=time.perf_counter() - start,
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
        _record_usage(
            operation="llm.acomplete_structured",
            model=resolved_model,
            latency_seconds=0.0,
            cache_hit=True,
        )
        return schema.model_validate_json(cached)

    start = time.perf_counter()
    try:
        response = await _async_instructor_client().chat.completions.create(
            model=resolved_model,
            messages=messages,
            response_model=schema,
            max_tokens=resolved_max_tokens,
            temperature=resolved_temperature,
            max_retries=settings.retry_max_attempts,
            **kwargs,
        )
    except Exception as exc:
        _record_usage(
            operation="llm.acomplete_structured",
            model=resolved_model,
            latency_seconds=time.perf_counter() - start,
            error=exc,
        )
        raise

    _record_usage(
        operation="llm.acomplete_structured",
        model=resolved_model,
        latency_seconds=time.perf_counter() - start,
    )
    result = cast(T, response)
    write_cached_json(cache_key, result.model_dump_json())
    return result

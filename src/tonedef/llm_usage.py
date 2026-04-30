from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from pydantic import BaseModel, ConfigDict, Field


class LLMUsageRecord(BaseModel):
    """Non-content metadata for one LLM client call."""

    model_config = ConfigDict(strict=True)

    operation: str = Field(description="Logical client operation, e.g. llm.complete.")
    model: str = Field(description="Provider/model string used for the call.")
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    latency_seconds: float = Field(ge=0.0)
    cache_hit: bool = False
    error: str | None = None


class LLMUsageSummary(BaseModel):
    """Aggregate LLM usage for a request or workflow."""

    model_config = ConfigDict(strict=True)

    records: list[LLMUsageRecord] = Field(default_factory=list)
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    provider_call_count: int = 0
    cache_hit_count: int = 0
    total_latency_seconds: float = 0.0


class LLMUsageCollector:
    """Collect usage records from client calls within a context."""

    def __init__(self) -> None:
        self.records: list[LLMUsageRecord] = []

    def add(self, record: LLMUsageRecord) -> None:
        self.records.append(record)

    def summary(self) -> LLMUsageSummary:
        return summarize_usage(self.records)


_current_collector: ContextVar[LLMUsageCollector | None] = ContextVar(
    "tonedef_llm_usage_collector",
    default=None,
)


@contextmanager
def collect_llm_usage() -> Iterator[LLMUsageCollector]:
    """Collect LLM usage records produced inside this context."""
    collector = LLMUsageCollector()
    token = _current_collector.set(collector)
    try:
        yield collector
    finally:
        _current_collector.reset(token)


def record_llm_usage(record: LLMUsageRecord) -> None:
    """Record usage if a collector is active."""
    collector = _current_collector.get()
    if collector is not None:
        collector.add(record)


def summarize_usage(records: list[LLMUsageRecord]) -> LLMUsageSummary:
    """Summarize records while treating missing token/cost fields as zero."""
    return LLMUsageSummary(
        records=list(records),
        total_prompt_tokens=sum(r.prompt_tokens or 0 for r in records),
        total_completion_tokens=sum(r.completion_tokens or 0 for r in records),
        total_tokens=sum(r.total_tokens or 0 for r in records),
        estimated_cost_usd=sum(r.estimated_cost_usd or 0.0 for r in records),
        provider_call_count=sum(1 for r in records if not r.cache_hit),
        cache_hit_count=sum(1 for r in records if r.cache_hit),
        total_latency_seconds=sum(r.latency_seconds for r in records),
    )

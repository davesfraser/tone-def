from __future__ import annotations

from tonedef.llm_usage import LLMUsageRecord, collect_llm_usage, summarize_usage


def test_collect_llm_usage_summarizes_records() -> None:
    with collect_llm_usage() as collector:
        collector.add(
            LLMUsageRecord(
                operation="llm.complete",
                model="test/model",
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                estimated_cost_usd=0.001,
                latency_seconds=0.25,
            )
        )
        collector.add(
            LLMUsageRecord(
                operation="llm.complete",
                model="test/model",
                estimated_cost_usd=0.0,
                latency_seconds=0.0,
                cache_hit=True,
            )
        )

    summary = collector.summary()

    assert summary.total_prompt_tokens == 10
    assert summary.total_completion_tokens == 5
    assert summary.total_tokens == 15
    assert summary.estimated_cost_usd == 0.001
    assert summary.provider_call_count == 1
    assert summary.cache_hit_count == 1
    assert summary.total_latency_seconds == 0.25


def test_summarize_usage_treats_missing_values_as_zero() -> None:
    summary = summarize_usage(
        [
            LLMUsageRecord(
                operation="llm.complete",
                model="test/model",
                latency_seconds=0.1,
            )
        ]
    )

    assert summary.total_tokens == 0
    assert summary.estimated_cost_usd == 0.0
    assert summary.provider_call_count == 1

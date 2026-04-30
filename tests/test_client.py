from __future__ import annotations

from types import SimpleNamespace

from pydantic import BaseModel
from tenacity import wait_none

from tonedef import client
from tonedef.cache import completion_cache_key, write_cached_completion
from tonedef.settings import settings


class DemoResponse(BaseModel):
    answer: str


def _text_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            ),
        ],
    )


def _text_response_with_usage(
    content: str,
    *,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    cost: float = 0.001,
) -> SimpleNamespace:
    response = _text_response(content)
    response.usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )
    response._hidden_params = {"response_cost": cost}
    return response


def test_complete_uses_litellm_without_network(monkeypatch, tmp_path) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    monkeypatch.setattr(settings, "cache_enabled", True)

    def fake_completion(**kwargs: object) -> SimpleNamespace:
        calls.append(dict(kwargs))
        return _text_response("hello")

    monkeypatch.setattr(client.litellm, "completion", fake_completion)

    result = client.complete([{"role": "user", "content": "Say hello"}], model="test/model")

    assert result == "hello"
    assert calls[0]["model"] == "test/model"
    assert calls[0]["timeout"] == settings.request_timeout_seconds


def test_complete_reads_cache_before_litellm(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    monkeypatch.setattr(settings, "cache_enabled", True)
    payload = client._completion_payload(
        [{"role": "user", "content": "Say hello"}],
        model="test/model",
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
        extra={},
    )
    cache_key = completion_cache_key(payload)
    write_cached_completion(cache_key, "cached hello")

    def fail_completion(**kwargs: object) -> None:
        raise AssertionError("LiteLLM should not be called on cache hit")

    monkeypatch.setattr(client.litellm, "completion", fail_completion)

    result = client.complete([{"role": "user", "content": "Say hello"}], model="test/model")

    assert result == "cached hello"


def test_complete_records_usage_metadata(monkeypatch, tmp_path) -> None:
    from tonedef.llm_usage import collect_llm_usage

    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    monkeypatch.setattr(settings, "cache_enabled", False)

    def fake_completion(**kwargs: object) -> SimpleNamespace:
        return _text_response_with_usage(
            "hello", prompt_tokens=12, completion_tokens=7, cost=0.0025
        )

    monkeypatch.setattr(client.litellm, "completion", fake_completion)

    with collect_llm_usage() as usage:
        result = client.complete([{"role": "user", "content": "Say hello"}], model="test/model")

    assert result == "hello"
    summary = usage.summary()
    assert summary.total_prompt_tokens == 12
    assert summary.total_completion_tokens == 7
    assert summary.total_tokens == 19
    assert summary.estimated_cost_usd == 0.0025
    assert summary.provider_call_count == 1
    assert summary.records[0].operation == "llm.complete"
    assert summary.records[0].model == "test/model"


def test_complete_records_cost_fallback(monkeypatch, tmp_path) -> None:
    from tonedef.llm_usage import collect_llm_usage

    response = _text_response_with_usage("hello")
    response._hidden_params = {}

    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    monkeypatch.setattr(settings, "cache_enabled", False)
    monkeypatch.setattr(client.litellm, "completion", lambda **kwargs: response)
    monkeypatch.setattr(
        client.litellm,
        "completion_cost",
        lambda completion_response: 0.003,
        raising=False,
    )

    with collect_llm_usage() as usage:
        client.complete([{"role": "user", "content": "Say hello"}], model="test/model")

    assert usage.summary().estimated_cost_usd == 0.003


def test_complete_records_missing_usage_without_error(monkeypatch, tmp_path) -> None:
    from tonedef.llm_usage import collect_llm_usage

    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    monkeypatch.setattr(settings, "cache_enabled", False)
    monkeypatch.setattr(client.litellm, "completion", lambda **kwargs: _text_response("hello"))
    monkeypatch.delattr(client.litellm, "completion_cost", raising=False)

    with collect_llm_usage() as usage:
        client.complete([{"role": "user", "content": "Say hello"}], model="test/model")

    record = usage.records[0]
    assert record.prompt_tokens is None
    assert record.completion_tokens is None
    assert record.total_tokens is None
    assert record.estimated_cost_usd is None


def test_complete_records_cache_hit_as_zero_cost(monkeypatch, tmp_path) -> None:
    from tonedef.llm_usage import collect_llm_usage

    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    monkeypatch.setattr(settings, "cache_enabled", True)
    payload = client._completion_payload(
        [{"role": "user", "content": "Say hello"}],
        model="test/model",
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
        extra={},
    )
    cache_key = completion_cache_key(payload)
    write_cached_completion(cache_key, "cached hello")

    with collect_llm_usage() as usage:
        result = client.complete([{"role": "user", "content": "Say hello"}], model="test/model")

    assert result == "cached hello"
    summary = usage.summary()
    assert summary.provider_call_count == 0
    assert summary.cache_hit_count == 1
    assert summary.estimated_cost_usd == 0.0
    assert summary.records[0].cache_hit is True


def test_complete_structured_uses_instructor(monkeypatch) -> None:
    expected = DemoResponse(answer="structured")
    client._instructor_client.cache_clear()

    class FakeCompletions:
        def create(self, **kwargs: object) -> DemoResponse:
            assert kwargs["response_model"] is DemoResponse
            return expected

    class FakeChat:
        completions = FakeCompletions()

    class FakeInstructorClient:
        chat = FakeChat()

    monkeypatch.setattr(
        client.instructor,
        "from_litellm",
        lambda completion: FakeInstructorClient(),
    )

    result = client.complete_structured(
        [{"role": "user", "content": "Extract"}],
        DemoResponse,
        model="test/model",
    )

    assert result == expected


def test_complete_structured_uses_cache(monkeypatch, tmp_path) -> None:
    expected = DemoResponse(answer="structured")
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    monkeypatch.setattr(settings, "cache_enabled", True)
    client._instructor_client.cache_clear()

    class FakeCompletions:
        calls = 0

        def create(self, **kwargs: object) -> DemoResponse:
            self.calls += 1
            return expected

    completions = FakeCompletions()

    class FakeChat:
        def __init__(self) -> None:
            self.completions = completions

    class FakeInstructorClient:
        def __init__(self) -> None:
            self.chat = FakeChat()

    monkeypatch.setattr(
        client.instructor,
        "from_litellm",
        lambda completion: FakeInstructorClient(),
    )

    first = client.complete_structured(
        [{"role": "user", "content": "Extract"}],
        DemoResponse,
        model="test/model",
    )
    second = client.complete_structured(
        [{"role": "user", "content": "Extract"}],
        DemoResponse,
        model="test/model",
    )

    assert first == expected
    assert second == expected
    assert completions.calls == 1


def test_retry_attempts_are_read_at_call_time(monkeypatch, tmp_path) -> None:
    calls = 0
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    monkeypatch.setattr(settings, "cache_enabled", True)
    monkeypatch.setattr(settings, "retry_max_attempts", 2)

    def fake_completion(**kwargs: object) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary failure")
        return _text_response("recovered")

    monkeypatch.setattr(client, "wait_exponential", lambda **kwargs: wait_none())
    monkeypatch.setattr(client.litellm, "completion", fake_completion)

    result = client.complete([{"role": "user", "content": "Say hello"}], model="test/model")

    assert result == "recovered"
    assert calls == 2

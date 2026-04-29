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

from __future__ import annotations

from tonedef import cache
from tonedef.settings import settings


def test_completion_cache_key_is_stable() -> None:
    first = cache.completion_cache_key({"model": "demo", "messages": [{"role": "user"}]})
    second = cache.completion_cache_key({"messages": [{"role": "user"}], "model": "demo"})

    assert first == second


def test_completion_cache_round_trip(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    monkeypatch.setattr(settings, "cache_enabled", True)

    key = cache.completion_cache_key({"model": "demo"})
    assert cache.read_cached_completion(key) is None

    cache.write_cached_completion(key, "cached response")

    assert cache.read_cached_completion(key) == "cached response"


def test_completion_cache_respects_disabled_setting(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    monkeypatch.setattr(settings, "cache_enabled", False)

    key = cache.completion_cache_key({"model": "demo"})
    cache.write_cached_completion(key, "cached response")

    assert cache.read_cached_completion(key) is None
    assert not list(tmp_path.iterdir())

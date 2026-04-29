from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tonedef.paths import project_root
from tonedef.settings import settings


def completion_cache_key(payload: Mapping[str, Any]) -> str:
    """Return a stable cache key for an LLM request payload."""
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _cache_dir() -> Path:
    cache_dir = settings.cache_dir
    return cache_dir if cache_dir.is_absolute() else project_root() / cache_dir


def _cache_path(key: str) -> Path:
    return _cache_dir() / f"{key}.json"


def read_cached_completion(key: str) -> str | None:
    """Read a cached text completion, returning None when no usable cache exists."""
    if not settings.cache_enabled:
        return None

    path = _cache_path(key)
    if not path.exists():
        return None

    data = json.loads(path.read_text(encoding="utf-8"))
    value = data.get("content")
    return value if isinstance(value, str) else None


def write_cached_completion(key: str, content: str) -> None:
    """Persist a text completion for local repeatability."""
    if not settings.cache_enabled:
        return

    cache_dir = _cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    _cache_path(key).write_text(
        json.dumps({"content": content}, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def read_cached_json(key: str) -> str | None:
    """Read a cached JSON payload."""
    return read_cached_completion(key)


def write_cached_json(key: str, content: str) -> None:
    """Persist a JSON payload in the same local cache as text completions."""
    write_cached_completion(key, content)

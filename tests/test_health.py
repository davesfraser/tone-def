"""Tests for tonedef.health pipeline checks."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from tonedef.health import (
    check_env,
    check_files,
    check_schema_integrity,
    check_staleness,
    newest_mtime,
)

# ---------------------------------------------------------------------------
# newest_mtime
# ---------------------------------------------------------------------------


def test_newest_mtime_nonexistent(tmp_path: Path) -> None:
    """Returns 0.0 for paths that don't exist."""
    assert newest_mtime(tmp_path / "nope") == 0.0


def test_newest_mtime_single_file(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("hi")
    assert newest_mtime(f) == f.stat().st_mtime


def test_newest_mtime_directory(tmp_path: Path) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("first")
    b.write_text("second")
    result = newest_mtime(tmp_path)
    assert result == max(a.stat().st_mtime, b.stat().st_mtime)


def test_newest_mtime_mixed(tmp_path: Path) -> None:
    existing = tmp_path / "yes.txt"
    existing.write_text("here")
    missing = tmp_path / "no.txt"
    result = newest_mtime(existing, missing)
    assert result == existing.stat().st_mtime


# ---------------------------------------------------------------------------
# check_files
# ---------------------------------------------------------------------------


def test_check_files_all_present(tmp_path: Path) -> None:
    f = tmp_path / "data.json"
    f.write_text("x" * 200)
    issues = check_files([("Test file", f, 100, "rebuild")])
    assert issues == []


def test_check_files_missing(tmp_path: Path) -> None:
    issues = check_files([("Missing", tmp_path / "nope.json", 10, "fix-cmd")])
    assert len(issues) == 1
    assert "fix-cmd" in issues[0]


def test_check_files_too_small(tmp_path: Path) -> None:
    f = tmp_path / "tiny.json"
    f.write_text("x")
    issues = check_files([("Tiny", f, 1000, "rebuild")])
    assert len(issues) == 1
    assert "may be empty" in issues[0]


# ---------------------------------------------------------------------------
# check_schema_integrity
# ---------------------------------------------------------------------------


def test_check_schema_integrity_ok(tmp_path: Path) -> None:
    schema_path = tmp_path / "component_schema.json"
    lookup_path = tmp_path / "amp_cabinet_lookup.json"
    schema_path.write_text(json.dumps({"a": 1, "b": 2}))
    lookup_path.write_text(json.dumps({"x": 1}))

    with patch("tonedef.health.DATA_PROCESSED", tmp_path):
        issues = check_schema_integrity()
    assert issues == []


def test_check_schema_integrity_missing(tmp_path: Path) -> None:
    with patch("tonedef.health.DATA_PROCESSED", tmp_path):
        issues = check_schema_integrity()
    assert len(issues) == 2


# ---------------------------------------------------------------------------
# check_env
# ---------------------------------------------------------------------------


def test_check_env_valid_key() -> None:
    from pydantic import SecretStr

    mock_settings = type("S", (), {"anthropic_api_key": SecretStr("sk-ant-test123")})()
    with patch("tonedef.health.settings", mock_settings):
        issues = check_env()
    assert issues == []


def test_check_env_empty_key() -> None:
    from pydantic import SecretStr

    mock_settings = type("S", (), {"anthropic_api_key": SecretStr("")})()
    with patch("tonedef.health.settings", mock_settings):
        issues = check_env()
    assert len(issues) == 1
    assert "ANTHROPIC_API_KEY" in issues[0]


def test_check_env_wrong_prefix() -> None:
    from pydantic import SecretStr

    mock_settings = type("S", (), {"anthropic_api_key": SecretStr("your-key-here")})()
    with patch("tonedef.health.settings", mock_settings):
        issues = check_env()
    assert len(issues) == 1


# ---------------------------------------------------------------------------
# check_staleness
# ---------------------------------------------------------------------------


def test_check_staleness_up_to_date(tmp_path: Path) -> None:
    dep = tmp_path / "source.py"
    dep.write_text("old")
    artifact = tmp_path / "output.json"
    artifact.write_text("new")

    staleness_map = [(artifact, "Output", [dep])]
    issues = check_staleness(staleness_map)
    assert issues == []


def test_check_staleness_stale(tmp_path: Path) -> None:
    import time

    artifact = tmp_path / "output.json"
    artifact.write_text("old")
    time.sleep(0.05)
    dep = tmp_path / "source.py"
    dep.write_text("newer")

    staleness_map = [(artifact, "Output", [dep])]
    issues = check_staleness(staleness_map)
    assert len(issues) == 1
    assert "stale" in issues[0]


def test_check_staleness_missing_artifact(tmp_path: Path) -> None:
    """Missing artefacts are silently skipped (reported by check_files)."""
    dep = tmp_path / "source.py"
    dep.write_text("exists")
    staleness_map = [(tmp_path / "nope.json", "Missing", [dep])]
    issues = check_staleness(staleness_map)
    assert issues == []

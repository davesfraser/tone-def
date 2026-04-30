from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from tonedef.paths import EVALS_DATASETS_DIR, EVALS_GOLDEN_DIR

_FIXTURE_PAIRS = {
    "prompt_rendering": (
        EVALS_DATASETS_DIR / "prompt_rendering.jsonl",
        EVALS_GOLDEN_DIR / "prompt_rendering_expected.json",
    ),
    "retrieval_quality": (
        EVALS_DATASETS_DIR / "retrieval_quality.jsonl",
        EVALS_GOLDEN_DIR / "retrieval_quality_expected.json",
    ),
    "preset_component_validity": (
        EVALS_DATASETS_DIR / "preset_component_validity.jsonl",
        EVALS_GOLDEN_DIR / "preset_component_validity_expected.json",
    ),
}


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        assert isinstance(row, dict), f"{path}:{line_number} must contain a JSON object"
        rows.append(row)
    return rows


def _read_json_object(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path} must contain a JSON object"
    return data


def _assert_keys(row: dict[str, object], keys: Iterable[str]) -> None:
    missing = [key for key in keys if key not in row]
    assert not missing, f"{row.get('id', '<missing id>')} missing keys: {missing}"


def test_eval_fixture_files_parse_and_ids_match_golden() -> None:
    for dataset_path, golden_path in _FIXTURE_PAIRS.values():
        rows = _read_jsonl(dataset_path)
        golden = _read_json_object(golden_path)

        row_ids = {row["id"] for row in rows}
        assert row_ids == set(golden), f"{dataset_path.name} IDs must match {golden_path.name}"


def test_prompt_rendering_fixture_contract() -> None:
    rows = _read_jsonl(_FIXTURE_PAIRS["prompt_rendering"][0])
    golden = _read_json_object(_FIXTURE_PAIRS["prompt_rendering"][1])

    for row in rows:
        _assert_keys(row, ["id", "template", "assertions"])
        expected = golden[str(row["id"])]
        assert isinstance(expected, dict)
        assert "must_not_contain" in expected or "required_context_keys" in expected


def test_retrieval_quality_fixture_contract() -> None:
    rows = _read_jsonl(_FIXTURE_PAIRS["retrieval_quality"][0])
    golden = _read_json_object(_FIXTURE_PAIRS["retrieval_quality"][1])

    for row in rows:
        _assert_keys(
            row,
            ["id", "query", "expected_tags", "expected_components", "min_relevant_exemplars"],
        )
        expected = golden[str(row["id"])]
        assert isinstance(expected, dict)
        assert expected["expected_tags"] == row["expected_tags"]
        assert expected["expected_components"] == row["expected_components"]


def test_preset_component_validity_fixture_contract() -> None:
    rows = _read_jsonl(_FIXTURE_PAIRS["preset_component_validity"][0])
    golden = _read_json_object(_FIXTURE_PAIRS["preset_component_validity"][1])

    for row in rows:
        expected = golden[str(row["id"])]
        assert isinstance(expected, dict)
        if "input_components" in row:
            _assert_keys(row, ["id", "input_components", "required_components", "assertions"])
            assert expected["required_components"] == row["required_components"]
            assert expected["checks"] == row["assertions"]
        else:
            _assert_keys(row, ["id", "query", "expected_component_types", "required_assertions"])
            assert expected["expected_component_types"] == row["expected_component_types"]
            assert expected["checks"] == row["required_assertions"]

"""
Tests for tonedef.exemplar_store

All tests use synthetic in-memory data — no .ngrr files required.
"""

from __future__ import annotations

import pytest

from tonedef.exemplar_store import (
    _invert_tag_catalogue,
    build_exemplar_records,
    format_exemplar_context,
)
from tonedef.paths import DATA_EXTERNAL

# ---------------------------------------------------------------------------
# _invert_tag_catalogue
# ---------------------------------------------------------------------------

_TAG_CATALOGUE = [
    {
        "value": "Blues",
        "root": "Genres",
        "seen_in_presets": ["Beano", "SRV Tone"],
    },
    {
        "value": "Clean",
        "root": "Characters",
        "seen_in_presets": ["Beano", "Crystal Clean"],
    },
    {
        "value": "Distortion",
        "root": "FX Types",
        "seen_in_presets": ["Metal Machine"],
    },
]


def test_invert_tag_catalogue_groups_by_preset() -> None:
    result = _invert_tag_catalogue(_TAG_CATALOGUE)
    assert "Beano" in result
    assert set(result["Beano"]) == {"Blues", "Clean"}


def test_invert_tag_catalogue_single_tag_preset() -> None:
    result = _invert_tag_catalogue(_TAG_CATALOGUE)
    assert result["Metal Machine"] == ["Distortion"]


def test_invert_tag_catalogue_empty_input() -> None:
    result = _invert_tag_catalogue([])
    assert result == {}


def test_invert_tag_catalogue_missing_seen_in_presets() -> None:
    catalogue = [{"value": "Rock", "root": "Genres"}]  # no seen_in_presets key
    result = _invert_tag_catalogue(catalogue)
    assert result == {}


# ---------------------------------------------------------------------------
# format_exemplar_context
# ---------------------------------------------------------------------------

_EXEMPLAR_RECORDS = [
    {
        "preset_name": "Blues Crunch",
        "tags": ["Blues", "Crunch"],
        "components": [
            {
                "component_name": "Tweed Delight",
                "component_id": 79000,
                "parameters": {"vb": 0.64, "vo": 0.5},
            }
        ],
    },
    {
        "preset_name": "Clean Shimmer",
        "tags": [],
        "components": [
            {
                "component_name": "Treble Booster",
                "component_id": 40000,
                "parameters": {"gn": 0.3},
            }
        ],
    },
]


def test_format_exemplar_context_returns_string() -> None:
    result = format_exemplar_context(_EXEMPLAR_RECORDS)
    assert isinstance(result, str)


def test_format_exemplar_context_contains_preset_name() -> None:
    result = format_exemplar_context(_EXEMPLAR_RECORDS)
    assert "Blues Crunch" in result
    assert "Clean Shimmer" in result


def test_format_exemplar_context_contains_tags() -> None:
    result = format_exemplar_context(_EXEMPLAR_RECORDS)
    assert "Blues" in result
    assert "Crunch" in result


def test_format_exemplar_context_untagged_label() -> None:
    result = format_exemplar_context(_EXEMPLAR_RECORDS)
    assert "untagged" in result


def test_format_exemplar_context_contains_component_name() -> None:
    result = format_exemplar_context(_EXEMPLAR_RECORDS)
    assert "Tweed Delight" in result


def test_format_exemplar_context_contains_param_values() -> None:
    result = format_exemplar_context(_EXEMPLAR_RECORDS)
    # param values formatted as "pid=0.64"
    assert "vb=0.64" in result


def test_format_exemplar_context_empty_returns_sentinel() -> None:
    result = format_exemplar_context([])
    assert result == "(no exemplars available)"


def test_format_exemplar_context_multiple_records_separated() -> None:
    result = format_exemplar_context(_EXEMPLAR_RECORDS)
    # Two records should produce two sections separated by blank line
    assert "\n\n" in result


# ---------------------------------------------------------------------------
# build_exemplar_records integration test (requires preset files on disk)
# ---------------------------------------------------------------------------

_PRESETS_DIR = DATA_EXTERNAL / "presets"


@pytest.mark.skipif(
    not _PRESETS_DIR.exists() or not any(_PRESETS_DIR.glob("*.ngrr")),
    reason="Factory presets not present in data/external/presets/",
)
def test_build_exemplar_records_returns_non_empty_list() -> None:
    tag_catalogue = [
        {"value": "Blues", "root": "Genres", "seen_in_presets": []},
    ]
    schema: dict = {}
    records = build_exemplar_records(_PRESETS_DIR, tag_catalogue, schema)
    assert len(records) > 0


@pytest.mark.skipif(
    not _PRESETS_DIR.exists() or not any(_PRESETS_DIR.glob("*.ngrr")),
    reason="Factory presets not present in data/external/presets/",
)
def test_build_exemplar_records_record_structure() -> None:
    tag_catalogue: list[dict] = []
    schema: dict = {}
    records = build_exemplar_records(_PRESETS_DIR, tag_catalogue, schema)
    for record in records[:5]:
        assert "preset_name" in record
        assert "tags" in record
        assert "components" in record
        assert isinstance(record["tags"], list)
        assert isinstance(record["components"], list)


@pytest.mark.skipif(
    not _PRESETS_DIR.exists() or not any(_PRESETS_DIR.glob("*.ngrr")),
    reason="Factory presets not present in data/external/presets/",
)
def test_build_exemplar_records_parameters_are_dicts() -> None:
    tag_catalogue: list[dict] = []
    schema: dict = {}
    records = build_exemplar_records(_PRESETS_DIR, tag_catalogue, schema)
    for record in records[:5]:
        for comp in record["components"]:
            assert isinstance(comp["parameters"], dict)
            for val in comp["parameters"].values():
                assert isinstance(val, float)


@pytest.mark.skipif(
    not _PRESETS_DIR.exists() or not any(_PRESETS_DIR.glob("*.ngrr")),
    reason="Factory presets not present in data/external/presets/",
)
def test_build_exemplar_records_tags_come_from_catalogue() -> None:
    tag_catalogue = [
        {
            "value": "TestTag",
            "root": "Genres",
            "seen_in_presets": [],
        }
    ]
    # Get the first real preset name from disk
    preset_path = sorted(_PRESETS_DIR.glob("*.ngrr"))[0]
    from tonedef.ngrr_parser import extract_preset_name

    first_name = extract_preset_name(preset_path)
    tag_catalogue[0]["seen_in_presets"] = [first_name]

    schema: dict = {}
    records = build_exemplar_records(_PRESETS_DIR, tag_catalogue, schema)
    matching = [r for r in records if r["preset_name"] == first_name]
    assert len(matching) == 1
    assert "TestTag" in matching[0]["tags"]

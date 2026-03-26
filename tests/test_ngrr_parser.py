"""
Tests for tonedef.ngrr_parser

All tests operate on synthetic in-memory data — no .ngrr files on disk required.
"""

from __future__ import annotations

import statistics

import pytest

from tonedef.ngrr_parser import (
    INCLUDED_TAG_ROOTS,
    finalise_catalogue,
    merge_into_catalogue,
    merge_tags_into_catalogue,
    parse_non_fix_components,
    parse_preset_metadata,
)

# ---------------------------------------------------------------------------
# parse_non_fix_components
# ---------------------------------------------------------------------------

_XML2_ONE_COMPONENT = """\
<?xml version="1.0" encoding="UTF-8"?>
<gr-instrument-chunk>
  <non-fix-components>
    <component id="79000" name="Tweed Delight">
      <component-audio version="2">
        <parameters>
          <parameter id="vb" name="Bright" value="0.64"/>
          <parameter id="vo" name="Volume" value="0.5"/>
        </parameters>
      </component-audio>
    </component>
  </non-fix-components>
</gr-instrument-chunk>
"""

_XML2_TWO_COMPONENTS = """\
<?xml version="1.0" encoding="UTF-8"?>
<gr-instrument-chunk>
  <non-fix-components>
    <component id="10000" name="Fuzz Face">
      <component-audio version="2">
        <parameters>
          <parameter id="fz" name="Fuzz" value="0.8"/>
        </parameters>
      </component-audio>
    </component>
    <component id="20000" name="Spring Reverb">
      <component-audio version="2">
        <parameters>
          <parameter id="rv" name="Reverb" value="0.3"/>
          <parameter id="mx" name="Mix" value="0.5"/>
        </parameters>
      </component-audio>
    </component>
  </non-fix-components>
</gr-instrument-chunk>
"""

_XML2_NO_NON_FIX = """\
<?xml version="1.0" encoding="UTF-8"?>
<gr-instrument-chunk>
  <fix-components/>
</gr-instrument-chunk>
"""

_XML2_BAD_PARAM_VALUE = """\
<?xml version="1.0" encoding="UTF-8"?>
<gr-instrument-chunk>
  <non-fix-components>
    <component id="1" name="Widget">
      <component-audio version="2">
        <parameters>
          <parameter id="x" name="X" value="not-a-float"/>
        </parameters>
      </component-audio>
    </component>
  </non-fix-components>
</gr-instrument-chunk>
"""


def test_parse_non_fix_single_component() -> None:
    result = parse_non_fix_components(_XML2_ONE_COMPONENT)
    assert len(result) == 1
    comp = result[0]
    assert comp["component_name"] == "Tweed Delight"
    assert comp["component_id"] == 79000
    assert len(comp["parameters"]) == 2


def test_parse_non_fix_parameter_values() -> None:
    result = parse_non_fix_components(_XML2_ONE_COMPONENT)
    params = {p["param_id"]: p["value"] for p in result[0]["parameters"]}
    assert params["vb"] == pytest.approx(0.64)
    assert params["vo"] == pytest.approx(0.5)


def test_parse_non_fix_two_components_order() -> None:
    result = parse_non_fix_components(_XML2_TWO_COMPONENTS)
    assert len(result) == 2
    assert result[0]["component_name"] == "Fuzz Face"
    assert result[1]["component_name"] == "Spring Reverb"


def test_parse_non_fix_returns_empty_when_no_block() -> None:
    result = parse_non_fix_components(_XML2_NO_NON_FIX)
    assert result == []


def test_parse_non_fix_returns_empty_on_malformed_xml() -> None:
    result = parse_non_fix_components("this is not xml <<<")
    assert result == []


def test_parse_non_fix_bad_param_value_defaults_to_zero() -> None:
    result = parse_non_fix_components(_XML2_BAD_PARAM_VALUE)
    assert result[0]["parameters"][0]["value"] == pytest.approx(0.0)


def test_parse_non_fix_bad_component_id_defaults_to_zero() -> None:
    xml = _XML2_ONE_COMPONENT.replace('id="79000"', 'id="nope"')
    result = parse_non_fix_components(xml)
    assert result[0]["component_id"] == 0


# ---------------------------------------------------------------------------
# merge_into_catalogue / finalise_catalogue
# ---------------------------------------------------------------------------

_COMPONENTS_A = [
    {
        "component_name": "Tweed Amp",
        "component_id": 100,
        "parameters": [{"param_id": "vol", "param_name": "Volume", "value": 0.5}],
    }
]

_COMPONENTS_B = [
    {
        "component_name": "Tweed Amp",
        "component_id": 100,
        "parameters": [{"param_id": "vol", "param_name": "Volume", "value": 0.7}],
    }
]


def test_merge_adds_new_component() -> None:
    catalogue: dict = {}
    result = merge_into_catalogue(catalogue, _COMPONENTS_A, "Preset 1")
    assert "Tweed Amp" in result
    assert result["Tweed Amp"]["occurrence_count"] == 1


def test_merge_increments_occurrence_count() -> None:
    catalogue: dict = {}
    merge_into_catalogue(catalogue, _COMPONENTS_A, "Preset 1")
    merge_into_catalogue(catalogue, _COMPONENTS_B, "Preset 2")
    assert catalogue["Tweed Amp"]["occurrence_count"] == 2


def test_merge_accumulates_seen_values() -> None:
    catalogue: dict = {}
    merge_into_catalogue(catalogue, _COMPONENTS_A, "Preset 1")
    merge_into_catalogue(catalogue, _COMPONENTS_B, "Preset 2")
    seen = catalogue["Tweed Amp"]["parameters"]["vol"]["seen_values"]
    assert 0.5 in seen
    assert 0.7 in seen


def test_merge_keeps_duplicate_values() -> None:
    catalogue: dict = {}
    merge_into_catalogue(catalogue, _COMPONENTS_A, "Preset 1")
    merge_into_catalogue(catalogue, _COMPONENTS_A, "Preset 1")
    seen = catalogue["Tweed Amp"]["parameters"]["vol"]["seen_values"]
    assert seen.count(0.5) == 2


def test_merge_preset_name_not_duplicated() -> None:
    catalogue: dict = {}
    merge_into_catalogue(catalogue, _COMPONENTS_A, "Preset 1")
    merge_into_catalogue(catalogue, _COMPONENTS_A, "Preset 1")
    assert catalogue["Tweed Amp"]["seen_in_presets"].count("Preset 1") == 1


def test_finalise_catalogue_produces_list_params() -> None:
    catalogue: dict = {}
    merge_into_catalogue(catalogue, _COMPONENTS_A, "P1")
    merge_into_catalogue(catalogue, _COMPONENTS_B, "P2")
    finalised = finalise_catalogue(catalogue)
    params = finalised["Tweed Amp"]["parameters"]
    assert isinstance(params, list)
    assert params[0]["stats"]["count"] == 2
    assert "mode" in params[0]["stats"]
    assert "mode_count" in params[0]["stats"]


def test_finalise_default_uses_mode_when_strong() -> None:
    """Mode used as default when it accounts for >=15% of observations."""
    catalogue: dict = {}
    # 8 presets with value 0.5, 2 with value 0.7 -> mode=0.5 at 80%
    comp_a = [
        {
            "component_name": "EQ",
            "component_id": 1,
            "parameters": [{"param_id": "g", "param_name": "Gain", "value": 0.5}],
        }
    ]
    comp_b = [
        {
            "component_name": "EQ",
            "component_id": 1,
            "parameters": [{"param_id": "g", "param_name": "Gain", "value": 0.7}],
        }
    ]
    for _ in range(8):
        merge_into_catalogue(catalogue, comp_a, f"P{_}")
    for _ in range(2):
        merge_into_catalogue(catalogue, comp_b, f"Q{_}")
    finalised = finalise_catalogue(catalogue)
    assert finalised["EQ"]["parameters"][0]["default_value"] == pytest.approx(0.5)


def test_finalise_default_falls_back_to_median_when_weak() -> None:
    """Median used as default when mode accounts for <15% of observations."""
    catalogue: dict = {}
    # 20 unique values -> each appears once -> mode_count/total = 1/20 = 5%
    for i in range(20):
        c = [
            {
                "component_name": "EQ",
                "component_id": 1,
                "parameters": [{"param_id": "g", "param_name": "Gain", "value": i / 20}],
            }
        ]
        merge_into_catalogue(catalogue, c, f"P{i}")
    finalised = finalise_catalogue(catalogue)
    param = finalised["EQ"]["parameters"][0]
    expected_median = round(statistics.median([i / 20 for i in range(20)]), 6)
    assert param["default_value"] == pytest.approx(expected_median)


def test_finalise_catalogue_sorted_keys() -> None:
    catalogue: dict = {}
    merge_into_catalogue(
        catalogue, [{"component_name": "Z Comp", "component_id": 2, "parameters": []}], "P"
    )
    merge_into_catalogue(
        catalogue, [{"component_name": "A Comp", "component_id": 1, "parameters": []}], "P"
    )
    finalised = finalise_catalogue(catalogue)
    keys = list(finalised.keys())
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# merge_tags_into_catalogue / finalise_tag_catalogue
# ---------------------------------------------------------------------------

_METADATA_ROCK = {
    "name": "Heavy Riff",
    "tags": [{"value": "Rock", "root": "Genres", "path": "Genres > Rock"}],
}

_METADATA_ROCK_2 = {
    "name": "Power Chord",
    "tags": [{"value": "Rock", "root": "Genres", "path": "Genres > Rock"}],
}


def test_merge_tags_adds_new_entry() -> None:
    catalogue: dict = {}
    result = merge_tags_into_catalogue(catalogue, _METADATA_ROCK)
    key = "Genres::Rock"
    assert key in result
    assert result[key]["occurrence_count"] == 1


def test_merge_tags_increments_count() -> None:
    catalogue: dict = {}
    merge_tags_into_catalogue(catalogue, _METADATA_ROCK)
    merge_tags_into_catalogue(catalogue, _METADATA_ROCK_2)
    assert catalogue["Genres::Rock"]["occurrence_count"] == 2


def test_merge_tags_preset_not_duplicated() -> None:
    catalogue: dict = {}
    merge_tags_into_catalogue(catalogue, _METADATA_ROCK)
    merge_tags_into_catalogue(catalogue, _METADATA_ROCK)
    assert catalogue["Genres::Rock"]["seen_in_presets"].count("Heavy Riff") == 1


def test_included_tag_roots_is_set() -> None:
    assert isinstance(INCLUDED_TAG_ROOTS, set)
    assert "Genres" in INCLUDED_TAG_ROOTS
    assert "Characters" in INCLUDED_TAG_ROOTS


# ---------------------------------------------------------------------------
# parse_preset_metadata
# ---------------------------------------------------------------------------

_XML1_FULL = """\
<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<guitarrig7-database-info>
  <soundinfo version="400">
    <properties>
      <name>Blues Crunch</name>
      <author>NativeInstruments</author>
      <comment>Classic blues crunch</comment>
    </properties>
    <attributes>
      <attribute>
        <value>factory</value>
        <user-set>RP://curated\tfactory</user-set>
      </attribute>
      <attribute>
        <value>Rock</value>
        <user-set>RP://Genres\tRock</user-set>
      </attribute>
      <attribute>
        <value>Amplifiers</value>
        <user-set>RP://Amplifiers</user-set>
      </attribute>
    </attributes>
  </soundinfo>
</guitarrig7-database-info>
"""


def test_parse_preset_metadata_name() -> None:
    result = parse_preset_metadata(_XML1_FULL)
    assert result["name"] == "Blues Crunch"


def test_parse_preset_metadata_is_factory() -> None:
    result = parse_preset_metadata(_XML1_FULL)
    assert result["is_factory"] is True


def test_parse_preset_metadata_tags_filtered_to_included_roots() -> None:
    result = parse_preset_metadata(_XML1_FULL)
    for tag in result["tags"]:
        assert tag["root"] in INCLUDED_TAG_ROOTS

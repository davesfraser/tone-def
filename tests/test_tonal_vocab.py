"""Tests for tonedef.tonal_vocab."""

from __future__ import annotations

from tonedef.tonal_vocab import (
    format_tonal_descriptors,
    get_all_selected_terms,
    get_ui_groups,
    get_zones_for_chain_type,
    load_descriptor_meta,
    load_tonal_descriptors,
)


def test_load_tonal_descriptors_has_all_zones() -> None:
    desc = load_tonal_descriptors()
    assert "pre_amp" in desc
    assert "amp" in desc
    assert "cabinet" in desc
    assert "room_mic" in desc
    assert "post_cab" in desc


def test_load_tonal_descriptors_entries_have_required_keys() -> None:
    desc = load_tonal_descriptors()
    required = {"term", "affects", "direction", "magnitude", "delta", "rationale"}
    for zone, entries in desc.items():
        for entry in entries:
            missing = required - set(entry.keys())
            assert not missing, f"{zone}: entry missing keys {missing}"


def test_get_zones_full_production() -> None:
    zones = get_zones_for_chain_type("FULL_PRODUCTION")
    assert "room_mic" in zones
    assert "pre_amp" in zones
    assert "amp" in zones
    assert "cabinet" in zones
    assert "post_cab" in zones


def test_get_zones_amp_only_includes_room_mic() -> None:
    zones = get_zones_for_chain_type("AMP_ONLY")
    assert "room_mic" in zones
    assert "pre_amp" in zones
    assert "amp" in zones


def test_format_includes_room_mic() -> None:
    result = format_tonal_descriptors()
    assert "ROOM & MICROPHONE" in result
    assert '"air"' in result


def test_format_includes_mic_tone() -> None:
    result = format_tonal_descriptors()
    assert '"silky"' in result
    assert '"aggressive"' in result
    assert '"detailed"' in result


def test_format_includes_common_descriptors() -> None:
    result = format_tonal_descriptors()
    assert '"brighter"' in result
    assert '"warmer"' in result
    assert '"grittier"' in result
    assert '"cleaner"' in result
    assert '"more ambient"' in result
    assert '"drier"' in result


def test_format_includes_expanded_cabinet_descriptors() -> None:
    result = format_tonal_descriptors()
    assert '"tight"' in result
    assert '"loose"' in result
    assert '"woody"' in result


def test_format_includes_expanded_mic_descriptors() -> None:
    result = format_tonal_descriptors()
    assert '"silky"' in result
    assert '"aggressive"' in result
    assert '"detailed"' in result


# -------------------------------------------------------------------
# load_tonal_descriptors excludes _meta
# -------------------------------------------------------------------


def test_load_excludes_meta_key() -> None:
    desc = load_tonal_descriptors()
    assert "_meta" not in desc


# -------------------------------------------------------------------
# load_descriptor_meta
# -------------------------------------------------------------------


def test_load_descriptor_meta_has_zones_and_groups() -> None:
    meta = load_descriptor_meta()
    assert "zones" in meta
    assert "groups" in meta
    assert "pre_amp" in meta["zones"]
    assert "amp" in meta["groups"]


def test_meta_zone_has_label_and_icon() -> None:
    meta = load_descriptor_meta()
    for zone_info in meta["zones"].values():
        assert "label" in zone_info
        assert "icon" in zone_info


# -------------------------------------------------------------------
# get_ui_groups
# -------------------------------------------------------------------


def test_get_ui_groups_pre_amp_has_three_groups() -> None:
    groups = get_ui_groups("pre_amp")
    names = [g["group"] for g in groups]
    assert "Gain Amount" in names
    assert "Drive Character" in names
    assert "Low End" in names


def test_get_ui_groups_options_have_required_fields() -> None:
    groups = get_ui_groups("amp")
    for group in groups:
        assert "group" in group
        assert "description" in group
        assert "options" in group
        for opt in group["options"]:
            assert "term" in opt
            assert "ui_label" in opt
            assert "ui_description" in opt


def test_get_ui_groups_preserves_order() -> None:
    """Groups appear in the same order as descriptors in the JSON."""
    groups = get_ui_groups("amp")
    names = [g["group"] for g in groups]
    assert names.index("Tone Balance") < names.index("Mid Range")
    assert names.index("Mid Range") < names.index("Gain Behavior")


def test_get_ui_groups_empty_zone_returns_empty() -> None:
    groups = get_ui_groups("nonexistent_zone")
    assert groups == []


def test_get_ui_groups_new_descriptors_present() -> None:
    """Verify the 7 new descriptors are accessible via get_ui_groups."""
    all_terms: list[str] = []
    for zone in ("pre_amp", "amp", "post_cab"):
        for group in get_ui_groups(zone):
            all_terms.extend(opt["term"] for opt in group["options"])
    for new_term in ("fuzzier", "sparkly", "honky", "glassy", "raw", "shimmery", "slapback"):
        assert new_term in all_terms, f"Missing new descriptor: {new_term}"


# -------------------------------------------------------------------
# get_all_selected_terms
# -------------------------------------------------------------------


def test_get_all_selected_terms_filters_none() -> None:
    selections = {
        "pre_amp__Gain Amount": "grittier",
        "amp__Tone Balance": None,
        "room_mic__Room Character": "roomy",
    }
    result = get_all_selected_terms(selections)
    assert result == ["grittier", "roomy"]


def test_get_all_selected_terms_empty_dict() -> None:
    assert get_all_selected_terms({}) == []


def test_get_all_selected_terms_all_none() -> None:
    selections = {"a": None, "b": None}
    assert get_all_selected_terms(selections) == []


# -------------------------------------------------------------------
# Descriptor entries have new UI fields
# -------------------------------------------------------------------


def test_all_descriptors_have_group_field() -> None:
    desc = load_tonal_descriptors()
    for zone, entries in desc.items():
        for entry in entries:
            assert "group" in entry, f"{zone}/{entry['term']} missing 'group'"


def test_all_descriptors_have_ui_fields() -> None:
    desc = load_tonal_descriptors()
    for zone, entries in desc.items():
        for entry in entries:
            assert "ui_label" in entry, f"{zone}/{entry['term']} missing 'ui_label'"
            assert "ui_description" in entry, f"{zone}/{entry['term']} missing 'ui_description'"


# -------------------------------------------------------------------
# Room/mic descriptors reference MCP X-Fade
# -------------------------------------------------------------------


def test_room_mic_placement_deltas_reference_mcp_xfade() -> None:
    """Mic Placement and Room Character deltas that affect distance must mention MCP X-Fade."""
    desc = load_tonal_descriptors()
    room_entries = desc["room_mic"]
    # "present" is a mic position/type selection (CRP-only), not a distance param
    distance_terms = [
        e
        for e in room_entries
        if (
            e["group"] in ("Mic Placement", "Room Character")
            and "mic_distance" in e.get("affects", [])
        )
        or e["group"] == "Room Character"
    ]
    for entry in distance_terms:
        assert "MCP X-Fade" in entry["delta"], (
            f"room_mic/{entry['term']} delta missing MCP X-Fade reference"
        )


def test_room_mic_format_includes_mcp_xfade() -> None:
    """Formatted output should contain MCP X-Fade guidance."""
    result = format_tonal_descriptors()
    assert "MCP X-Fade" in result

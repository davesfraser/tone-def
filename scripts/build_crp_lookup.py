# applied-skills: ds-workflow
"""Validate the hand-curated CRP enum lookup.

The CRP (Control Room Pro) enum data in data/processed/crp_enum_lookup.json
is static reference data derived from the Guitar Rig 7 Control Room Pro UI.
Cabinet naming is informed by Ali Jamieson's hardware equivalency mappings.

This script validates the file against expected counts and structure.
It does not generate the data — the file is hand-curated and committed.

Usage:
    uv run python scripts/build_crp_lookup.py
"""

from __future__ import annotations

from tonedef.crp_lookup import _CRP_LOOKUP_PATH, load_crp_enums

EXPECTED_CABINET_COUNT = 31  # 0-30
EXPECTED_MIC_COUNT = 5  # 0-4
EXPECTED_MPOS_COUNT = 3  # 0-2


def validate() -> None:
    """Validate the existing crp_enum_lookup.json against expectations."""
    enums = load_crp_enums()

    cabs = enums["cabinets"]
    mics = enums["microphones"]
    mpos = enums["mic_positions"]

    assert len(cabs) == EXPECTED_CABINET_COUNT, (
        f"Expected {EXPECTED_CABINET_COUNT} cabinets, got {len(cabs)}"
    )
    assert len(mics) == EXPECTED_MIC_COUNT, (
        f"Expected {EXPECTED_MIC_COUNT} microphones, got {len(mics)}"
    )
    assert len(mpos) == EXPECTED_MPOS_COUNT, (
        f"Expected {EXPECTED_MPOS_COUNT} mic positions, got {len(mpos)}"
    )

    # Keys must be contiguous integer strings starting at 0
    for label, data, count in [
        ("cabinets", cabs, EXPECTED_CABINET_COUNT),
        ("microphones", mics, EXPECTED_MIC_COUNT),
        ("mic_positions", mpos, EXPECTED_MPOS_COUNT),
    ]:
        expected_keys = {str(i) for i in range(count)}
        actual_keys = set(data.keys())
        assert actual_keys == expected_keys, (
            f"{label}: missing keys {expected_keys - actual_keys}, "
            f"extra keys {actual_keys - expected_keys}"
        )

    # Every entry must have name and description
    for label, data in [("cabinets", cabs), ("microphones", mics), ("mic_positions", mpos)]:
        for key, entry in data.items():
            assert "name" in entry, f"{label}[{key}] missing 'name'"
            assert "description" in entry, f"{label}[{key}] missing 'description'"

    print(f"Validated: {len(cabs)} cabinets, {len(mics)} mics, {len(mpos)} positions")
    print(f"File: {_CRP_LOOKUP_PATH}")


if __name__ == "__main__":
    if _CRP_LOOKUP_PATH.exists():
        print("crp_enum_lookup.json already exists — validating...")
        # Clear lru_cache so we read from disk
        load_crp_enums.cache_clear()
        validate()
    else:
        print(f"ERROR: {_CRP_LOOKUP_PATH} does not exist.")
        print("This is hand-curated reference data — it should be committed in data/processed/.")
        raise SystemExit(1)

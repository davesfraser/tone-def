"""Tests for tonedef.preset_builder."""

from __future__ import annotations

from tonedef.preset_builder import auto_preset_name


class TestAutoPresetName:
    def test_basic_query(self) -> None:
        assert auto_preset_name("warm clean tone") == "Warm Clean Tone"

    def test_strips_i_want_prefix(self) -> None:
        assert auto_preset_name("I want a smooth jazz tone") == "A Smooth Jazz Tone"

    def test_strips_give_me_prefix(self) -> None:
        assert auto_preset_name("give me heavy distortion") == "Heavy Distortion"

    def test_truncates_long_query(self) -> None:
        long_query = "a" * 100
        result = auto_preset_name(long_query)
        # 50 chars truncated, then title-cased
        assert len(result) == 50

    def test_empty_string_returns_default(self) -> None:
        assert auto_preset_name("") == "ToneDef Preset"

    def test_whitespace_only_returns_default(self) -> None:
        assert auto_preset_name("   ") == "ToneDef Preset"

    def test_strips_leading_trailing_whitespace(self) -> None:
        assert auto_preset_name("  crunchy blues  ") == "Crunchy Blues"

    def test_lowercase_i_want(self) -> None:
        assert auto_preset_name("i want something heavy") == "Something Heavy"

    def test_prefix_not_stripped_mid_string(self) -> None:
        result = auto_preset_name("what I want is crunch")
        assert result == "What I Want Is Crunch"

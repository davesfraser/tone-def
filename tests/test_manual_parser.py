"""Tests for tonedef.manual_parser."""

from __future__ import annotations

from tonedef.manual_parser import (
    CATEGORY_HEADERS,
    DESCRIPTION_KEYWORDS,
    is_artifact,
    parse_chunks,
)


class TestIsArtifact:
    def test_known_artifact(self) -> None:
        assert is_artifact("accordingly.") is True

    def test_when_prefix(self) -> None:
        assert is_artifact("When the button is pressed") is True

    def test_if_prefix(self) -> None:
        assert is_artifact("if you want more gain") is True

    def test_valid_component_name(self) -> None:
        assert is_artifact("Jump") is False

    def test_empty_string(self) -> None:
        assert is_artifact("") is False


class TestParseChunks:
    def test_single_component(self) -> None:
        text = "Amplifiers\nJump\nJump is a high-gain amplifier.\nGain: controls the gain."
        chunks = parse_chunks(text)
        assert "Jump" in chunks
        assert chunks["Jump"]["category"] == "Amplifiers"
        assert "high-gain" in chunks["Jump"]["text"]

    def test_multiple_components(self) -> None:
        text = (
            "Distortion\n"
            "Skreamer\n"
            "Skreamer is a classic overdrive.\nDrive: amount of drive.\n"
            "Cat\n"
            "Cat is a distortion pedal.\nGain: controls the gain."
        )
        chunks = parse_chunks(text)
        assert "Skreamer" in chunks
        assert "Cat" in chunks
        assert chunks["Skreamer"]["category"] == "Distortion"
        assert chunks["Cat"]["category"] == "Distortion"

    def test_category_switch(self) -> None:
        text = (
            "Amplifiers\n"
            "Jump\n"
            "Jump is a high-gain amplifier.\n"
            "Reverb\n"
            "Spring\n"
            "Spring is a reverb unit.\n"
        )
        chunks = parse_chunks(text)
        assert chunks["Jump"]["category"] == "Amplifiers"
        assert chunks["Spring"]["category"] == "Reverb"

    def test_empty_text_returns_empty(self) -> None:
        assert parse_chunks("") == {}

    def test_artifact_lines_excluded_as_names(self) -> None:
        text = "Amplifiers\naccordingly.\nJump\nJump is a high-gain amplifier."
        chunks = parse_chunks(text)
        assert "accordingly." not in chunks
        assert "Jump" in chunks


class TestConstants:
    def test_category_headers_are_frozenset(self) -> None:
        assert isinstance(CATEGORY_HEADERS, frozenset)

    def test_description_keywords_non_empty(self) -> None:
        assert len(DESCRIPTION_KEYWORDS) > 0

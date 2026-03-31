"""Tests for tonedef.signal_chain_parser."""

from __future__ import annotations

import pytest

from tonedef.signal_chain_parser import (
    ParsedSignalChain,
    format_tonal_target,
    parse_signal_chain,
)

# ---------------------------------------------------------------------------
# Fixtures — representative Phase 1 outputs
# ---------------------------------------------------------------------------

FULL_PRODUCTION_EXAMPLE = """\
<signal_chain>
Chain type: FULL_PRODUCTION — query references a specific recording

GUITAR SIGNAL CHAIN

[ Electro-Harmonix Memory Man — analog delay ] [DOCUMENTED]
  ◆ Delay time: dotted eighth note at song tempo (~490ms at 120bpm)
    └─ Creates the signature rhythmic pattern
  ◆ Feedback: 10 o'clock (estimated)
    └─ Enough repeats for texture
          ↓
[ Vox AC30 — tube amplifier ] [DOCUMENTED]  → (Guitar Rig: AC Box)
  ◆ Treble: 2 o'clock
    └─ Bright and present without harshness
  ◆ Bass: 10 o'clock
    └─ Restrained low end

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CABINET AND MIC

[ Vox 2x12 — open back cabinet ] [DOCUMENTED]
  ◆ Configuration: 2x12 open back
    └─ Open back for airy low end
  ◆ Speaker: Celestion Alnico Blue
    └─ Bright chiming top end
          ↓
[ Shure SM57 — dynamic microphone ] [INFERRED]
  ◆ Placement: edge of dust cap, slightly off-axis (estimated)
    └─ Off-axis softens presence peak

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECORDING CHAIN

[ Neve 1073 — microphone preamp and EQ ] [INFERRED]
  ◆ Gain: approximately +40dB (estimated)
    └─ Adds warmth at capture

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STUDIO PROCESSING

[ SSL G-series bus compressor — VCA compressor ] [INFERRED]
  ◆ Ratio: 2:1 (estimated)
    └─ Gentle cohesion

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHY THIS CHAIN WORKS
Edge's tone is built on rhythmic delay interacting with a lightly driven AC30.
The studio chain adds scale and space rather than character.

PLAYING NOTES
Clean, consistent picking is essential. Light pick attack with consistent
downstrokes on the intro figure.

CONFIDENCE: MEDIUM — guitar signal chain well documented; studio processing inferred

TAGS
Characters: Clean, Spacious
Genres: Rock, Alternative
</signal_chain>
"""

AMP_ONLY_EXAMPLE = """\
<signal_chain>
Chain type: AMP_ONLY — query references a general playing style

SIGNAL CHAIN

[ Tube Screamer — overdrive pedal ] [INFERRED]
  ◆ Drive: 3 o'clock
    └─ Pushes the amp into saturation
  ◆ Tone: 12 o'clock
    └─ Neutral midrange
  ◆ Volume: 2 o'clock
    └─ Slight volume boost
          ↓
[ Marshall JCM800 — tube amplifier ] [DOCUMENTED]  → (Guitar Rig: Lead 800)
  ◆ Preamp: 7
    └─ High gain for classic rock crunch
  ◆ Master: 5
    └─ Moderate volume

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CABINET AND MIC

[ Marshall 1960A — 4x12 closed back cabinet ] [DOCUMENTED]
  ◆ Speaker: Celestion Greenback
    └─ Classic British crunch character
          ↓
[ Shure SM57 — dynamic microphone ] [DOCUMENTED]
  ◆ Placement: on axis, edge of cone
    └─ Tight focused tone

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHY THIS CHAIN WORKS
The Tube Screamer tightens the low end before the Marshall, giving a focused
high-gain tone that cuts through the mix.

PLAYING NOTES
Use the bridge pickup for maximum bite. Palm muting benefits from the tight
low end.

CONFIDENCE: HIGH — well-documented classic setup

TAGS
Characters: Distorted
Genres: Rock, Metal
</signal_chain>
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParseFullProduction:
    @pytest.fixture()
    def parsed(self) -> ParsedSignalChain:
        return parse_signal_chain(FULL_PRODUCTION_EXAMPLE)

    def test_chain_type(self, parsed: ParsedSignalChain) -> None:
        assert parsed.chain_type == "FULL_PRODUCTION"

    def test_chain_type_reason(self, parsed: ParsedSignalChain) -> None:
        assert "specific recording" in parsed.chain_type_reason

    def test_section_count(self, parsed: ParsedSignalChain) -> None:
        assert len(parsed.sections) == 4

    def test_section_titles(self, parsed: ParsedSignalChain) -> None:
        titles = [s.title for s in parsed.sections]
        assert titles == [
            "Guitar Signal Chain",
            "Cabinet And Mic",
            "Recording Chain",
            "Studio Processing",
        ]

    def test_guitar_signal_chain_units(self, parsed: ParsedSignalChain) -> None:
        section = parsed.sections[0]
        assert len(section.units) == 2
        assert section.units[0].name == "Electro-Harmonix Memory Man"
        assert section.units[1].name == "Vox AC30"

    def test_unit_provenance(self, parsed: ParsedSignalChain) -> None:
        assert parsed.sections[0].units[0].provenance == "DOCUMENTED"
        assert parsed.sections[1].units[1].provenance == "INFERRED"

    def test_gr_equivalent(self, parsed: ParsedSignalChain) -> None:
        amp = parsed.sections[0].units[1]
        assert amp.gr_equivalent == "AC Box"

    def test_unit_parameters(self, parsed: ParsedSignalChain) -> None:
        delay = parsed.sections[0].units[0]
        assert len(delay.parameters) == 2
        assert delay.parameters[0].name == "Delay time"
        assert "490ms" in delay.parameters[0].value

    def test_parameter_explanation(self, parsed: ParsedSignalChain) -> None:
        delay = parsed.sections[0].units[0]
        assert "rhythmic pattern" in delay.parameters[0].explanation

    def test_recording_chain(self, parsed: ParsedSignalChain) -> None:
        recording = parsed.sections[2]
        assert recording.title == "Recording Chain"
        assert len(recording.units) == 1
        assert recording.units[0].name == "Neve 1073"

    def test_studio_processing(self, parsed: ParsedSignalChain) -> None:
        studio = parsed.sections[3]
        assert studio.title == "Studio Processing"
        assert len(studio.units) == 1

    def test_why_it_works(self, parsed: ParsedSignalChain) -> None:
        assert "rhythmic delay" in parsed.why_it_works

    def test_playing_notes(self, parsed: ParsedSignalChain) -> None:
        assert "consistent picking" in parsed.playing_notes

    def test_confidence(self, parsed: ParsedSignalChain) -> None:
        assert parsed.confidence == "MEDIUM"
        assert "documented" in parsed.confidence_detail

    def test_tags_characters(self, parsed: ParsedSignalChain) -> None:
        assert parsed.tags_characters == ["Clean", "Spacious"]

    def test_tags_genres(self, parsed: ParsedSignalChain) -> None:
        assert parsed.tags_genres == ["Rock", "Alternative"]


class TestParseAmpOnly:
    @pytest.fixture()
    def parsed(self) -> ParsedSignalChain:
        return parse_signal_chain(AMP_ONLY_EXAMPLE)

    def test_chain_type(self, parsed: ParsedSignalChain) -> None:
        assert parsed.chain_type == "AMP_ONLY"

    def test_section_count(self, parsed: ParsedSignalChain) -> None:
        assert len(parsed.sections) == 2

    def test_section_titles(self, parsed: ParsedSignalChain) -> None:
        titles = [s.title for s in parsed.sections]
        assert titles == ["Signal Chain", "Cabinet And Mic"]

    def test_tube_screamer_params(self, parsed: ParsedSignalChain) -> None:
        ts = parsed.sections[0].units[0]
        assert ts.name == "Tube Screamer"
        assert len(ts.parameters) == 3

    def test_gr_equivalent(self, parsed: ParsedSignalChain) -> None:
        amp = parsed.sections[0].units[1]
        assert amp.gr_equivalent == "Lead 800"

    def test_confidence_high(self, parsed: ParsedSignalChain) -> None:
        assert parsed.confidence == "HIGH"

    def test_tags(self, parsed: ParsedSignalChain) -> None:
        assert "Distorted" in parsed.tags_characters
        assert "Rock" in parsed.tags_genres
        assert "Metal" in parsed.tags_genres


class TestEdgeCases:
    def test_no_xml_tags(self) -> None:
        raw = "Chain type: AMP_ONLY — test\n\nSIGNAL CHAIN\n\n[ Amp — amplifier ] [DOCUMENTED]\n  ◆ Volume: 5\n    └─ Sets output level"
        result = parse_signal_chain(raw)
        assert result.chain_type == "AMP_ONLY"
        assert len(result.sections) == 1

    def test_empty_input(self) -> None:
        result = parse_signal_chain("")
        assert result.chain_type == "AMP_ONLY"
        assert result.sections == []

    def test_missing_confidence(self) -> None:
        raw = "<signal_chain>\nChain type: AMP_ONLY — test\n\nSIGNAL CHAIN\n\n[ Amp — amplifier ] [ESTIMATED]\n  ◆ Gain: 7\n    └─ High gain\n</signal_chain>"
        result = parse_signal_chain(raw)
        assert result.confidence == ""
        assert result.sections[0].units[0].provenance == "ESTIMATED"

    def test_unit_without_gr_equivalent(self) -> None:
        raw = "<signal_chain>\nChain type: AMP_ONLY — test\n\nSIGNAL CHAIN\n\n[ Boss DD-3 — digital delay ] [INFERRED]\n  ◆ Time: 350ms\n    └─ Quarter note delay\n</signal_chain>"
        result = parse_signal_chain(raw)
        assert result.sections[0].units[0].gr_equivalent is None

    def test_parameter_without_explanation(self) -> None:
        raw = "<signal_chain>\nChain type: AMP_ONLY — test\n\nSIGNAL CHAIN\n\n[ Amp — amplifier ] [DOCUMENTED]\n  ◆ Volume: 5\n  ◆ Gain: 7\n    └─ High gain\n</signal_chain>"
        result = parse_signal_chain(raw)
        unit = result.sections[0].units[0]
        assert unit.parameters[0].name == "Volume"
        assert unit.parameters[0].explanation == ""
        assert unit.parameters[1].explanation == "High gain"

    def test_approach_format_parses_reason(self) -> None:
        raw = "<signal_chain>\nApproach: warm lo-fi porch blues rig with tape degradation\n\nGUITAR SIGNAL CHAIN\n\n[ Fender Tweed — amplifier ] [INFERRED]\n  ◆ Volume: 7\n    └─ Pushed into saturation\n</signal_chain>"
        result = parse_signal_chain(raw)
        assert "lo-fi" in result.chain_type_reason
        assert result.chain_type == "AMP_ONLY"  # no recording/studio sections

    def test_approach_format_derives_full_production(self) -> None:
        raw = "<signal_chain>\nApproach: reconstructing the studio signal chain\n\nGUITAR SIGNAL CHAIN\n\n[ Amp — amplifier ] [DOCUMENTED]\n  ◆ Volume: 5\n    └─ Level\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n\nCABINET AND MIC\n\n[ Cab — cabinet ] [INFERRED]\n  ◆ Speaker: Greenback\n    └─ Crunch\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n\nRECORDING CHAIN\n\n[ Neve 1073 — preamp ] [INFERRED]\n  ◆ Gain: +40dB\n    └─ Warmth\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n\nSTUDIO PROCESSING\n\n[ SSL Compressor — compressor ] [ESTIMATED]\n  ◆ Ratio: 2:1\n    └─ Glue\n</signal_chain>"
        result = parse_signal_chain(raw)
        assert result.chain_type == "FULL_PRODUCTION"
        assert "studio signal chain" in result.chain_type_reason


# ---------------------------------------------------------------------------
# format_tonal_target
# ---------------------------------------------------------------------------


class TestFormatTonalTargetFullProduction:
    @pytest.fixture()
    def output(self) -> str:
        return format_tonal_target(parse_signal_chain(FULL_PRODUCTION_EXAMPLE))

    def test_contains_approach(self, output: str) -> None:
        assert "Approach:" in output or "Chain type:" in output

    def test_contains_unit_names(self, output: str) -> None:
        assert "Electro-Harmonix Memory Man" in output
        assert "Vox AC30" in output
        assert "Neve 1073" in output
        assert "SSL G-series bus compressor" in output

    def test_contains_gr_equivalents(self, output: str) -> None:
        assert "Guitar Rig: AC Box" in output

    def test_contains_param_values(self, output: str) -> None:
        assert "Delay time:" in output
        assert "490ms" in output
        assert "Treble: 2 o'clock" in output

    def test_contains_tags(self, output: str) -> None:
        assert "Characters: Clean, Spacious" in output
        assert "Genres: Rock, Alternative" in output

    def test_contains_section_headers(self, output: str) -> None:
        assert "GUITAR SIGNAL CHAIN" in output
        assert "CABINET AND MIC" in output
        assert "RECORDING CHAIN" in output
        assert "STUDIO PROCESSING" in output

    def test_excludes_provenance(self, output: str) -> None:
        assert "DOCUMENTED" not in output
        assert "INFERRED" not in output
        assert "ESTIMATED" not in output

    def test_includes_explanations(self, output: str) -> None:
        assert "└─" not in output  # decorative prefix stripped
        assert "rhythmic pattern" in output  # explanation text preserved

    def test_excludes_arrows(self, output: str) -> None:
        assert "↓" not in output

    def test_excludes_separators(self, output: str) -> None:
        assert "━" not in output

    def test_excludes_prose(self, output: str) -> None:
        assert "WHY THIS CHAIN WORKS" not in output
        assert "PLAYING NOTES" not in output
        assert "CONFIDENCE" not in output


class TestFormatTonalTargetAmpOnly:
    @pytest.fixture()
    def output(self) -> str:
        return format_tonal_target(parse_signal_chain(AMP_ONLY_EXAMPLE))

    def test_contains_approach(self, output: str) -> None:
        assert "Approach:" in output or "Chain type:" in output

    def test_contains_unit_names(self, output: str) -> None:
        assert "Tube Screamer" in output
        assert "Marshall JCM800" in output

    def test_contains_gr_equivalent(self, output: str) -> None:
        assert "Guitar Rig: Lead 800" in output

    def test_contains_tags(self, output: str) -> None:
        assert "Distorted" in output
        assert "Rock" in output
        assert "Metal" in output

    def test_excludes_provenance(self, output: str) -> None:
        assert "DOCUMENTED" not in output
        assert "INFERRED" not in output

    def test_includes_explanations(self, output: str) -> None:
        assert "└─" not in output  # decorative prefix stripped
        assert "Pushes the amp" in output  # explanation text preserved


class TestFormatTonalTargetEmpty:
    def test_empty_parsed_chain(self) -> None:
        parsed = parse_signal_chain("")
        output = format_tonal_target(parsed)
        assert "Chain type:" in output
        assert "TAGS" not in output

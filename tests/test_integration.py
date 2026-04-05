"""Integration test: full pipeline with mocked LLM responses.

Exercises compose_query → generate_signal_chain → parse_signal_chain →
validate_phase1 → map_components → build_preset without requiring a real
API key or ChromaDB index.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from tonedef.pipeline import compose_query, generate_signal_chain
from tonedef.preset_builder import build_preset
from tonedef.signal_chain_parser import parse_signal_chain
from tonedef.validation import validate_phase1

# ---------------------------------------------------------------------------
# Canned LLM responses
# ---------------------------------------------------------------------------

PHASE1_RAW = """\
<signal_chain>
Chain type: AMP_ONLY — query describes a general playing style

SIGNAL CHAIN

[ Tube Screamer — overdrive pedal ] [DOCUMENTED]  → (Guitar Rig: Skreamer)
  ◆ Drive: 3 o'clock
    └─ Pushes the amp into saturation
  ◆ Tone: 12 o'clock
    └─ Neutral midrange
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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHY THIS CHAIN WORKS
The Tube Screamer tightens the low end before the Marshall.

PLAYING NOTES
Use the bridge pickup.

CONFIDENCE: HIGH — well-documented classic setup

TAGS
Characters: Distorted
Genres: Rock
</signal_chain>
"""

PHASE2_JSON = """[
  {
    "component_name": "Skreamer",
    "component_id": 14000,
    "base_exemplar": "1993 Hot Solo Rig",
    "modification": "adjusted",
    "confidence": "documented",
    "rationale": "Classic TS-style drive",
    "description": "Tube Screamer clone",
    "parameters": {"vb": 0.75, "vi": 0.5, "vo": 0.65}
  },
  {
    "component_name": "Lead 800",
    "component_id": 56000,
    "base_exemplar": "1993 Hot Solo Rig",
    "modification": "adjusted",
    "confidence": "documented",
    "rationale": "Marshall JCM800 emulation",
    "description": "High-gain British amplifier",
    "parameters": {"vb": 0.6, "vi": 0.7, "vo": 0.5, "vd": 0.4}
  }
]"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _FakeUsage:
    input_tokens: int = 100
    output_tokens: int = 200


@dataclass
class _FakeContentBlock:
    text: str


@dataclass
class _FakeMessage:
    content: list[_FakeContentBlock]
    usage: _FakeUsage


def _make_fake_client(responses: list[str]) -> MagicMock:
    """Build a mock anthropic.Anthropic whose messages.create returns *responses* in order."""
    client = MagicMock()
    side_effects = [
        _FakeMessage(content=[_FakeContentBlock(text=r)], usage=_FakeUsage()) for r in responses
    ]
    client.messages.create.side_effect = side_effects
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_full_pipeline_produces_ngrr_bytes() -> None:
    """End-to-end pipeline: query → .ngrr bytes, all LLM calls mocked."""
    # Arrange
    query = "Classic rock crunch, Marshall JCM800 with a Tube Screamer in front"
    modifiers = ["grittier", "tighter"]
    client = _make_fake_client([PHASE1_RAW, PHASE2_JSON])

    # Phase 1
    composed = compose_query(query, modifiers)
    assert "Tonal modifiers:" in composed

    raw = generate_signal_chain(composed, client)
    assert raw == PHASE1_RAW

    parsed = parse_signal_chain(raw)
    assert parsed.chain_type == "AMP_ONLY"
    assert len(parsed.sections) >= 1

    p1v = validate_phase1(parsed)
    assert p1v is not None

    # Phase 2 — mock exemplar search to avoid ChromaDB dependency
    fake_exemplars = [
        {
            "preset_name": "1993 Hot Solo Rig",
            "tags": ["Distorted", "Rock"],
            "components": [
                {
                    "component_name": "Lead 800",
                    "component_id": 56000,
                    "parameters": {"vb": 0.5, "vi": 0.6},
                },
            ],
            "score": 0.85,
        },
    ]

    with patch("tonedef.component_mapper.search_exemplars", return_value=fake_exemplars):
        from tonedef.component_mapper import map_components

        components, _exemplars = map_components(raw, parsed, client)

    assert isinstance(components, list)
    assert len(components) >= 1

    # Every component should have a name and parameters
    for comp in components:
        assert "component_name" in comp
        assert "parameters" in comp

    # Phase 3 — build the .ngrr preset
    preset_bytes = build_preset(components, "Integration Test Preset")
    assert isinstance(preset_bytes, bytes)
    assert len(preset_bytes) > 0


@pytest.mark.integration
def test_pipeline_phase1_validation_returns_result() -> None:
    """Phase 1 validation produces a ValidationResult from parsed output."""
    client = _make_fake_client([PHASE1_RAW])

    raw = generate_signal_chain("test query", client)
    parsed = parse_signal_chain(raw)
    result = validate_phase1(parsed)

    # ValidationResult should always be returned (may have 0 errors/warnings)
    assert hasattr(result, "errors")
    assert hasattr(result, "warnings")
    assert isinstance(result.errors, list)
    assert isinstance(result.warnings, list)

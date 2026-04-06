"""Tests for tonedef.retriever structured exemplar matching."""

from __future__ import annotations

import pytest

from tonedef.paths import DATA_PROCESSED
from tonedef.retriever import (
    CONTROLLED_VOCAB,
    parse_signal_chain_components,
    parse_signal_chain_tags,
    score_exemplar,
    search_exemplars,
)

# ---------------------------------------------------------------------------
# Realistic Phase 1 output fixture (abridged but structurally accurate)
# ---------------------------------------------------------------------------

PHASE1_OUTPUT = """\
<signal_chain>
Chain type: AMP_ONLY — classic amp tone request

SIGNAL CHAIN

[ Tube Screamer — overdrive pedal ] [INFERRED]
  ◆ Drive: 3 o'clock
    └─ Moderate gain staging before the amp
  ◆ Tone: 1 o'clock
    └─ Mid-forward EQ push
          ↓
[ Lead 800 — tube amplifier ] [DOCUMENTED]
  ◆ Preamp: 7 o'clock
    └─ High gain crunch territory
  ◆ Master: 5 o'clock
    └─ Moderate output volume

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CABINET AND MIC

[ 4x12 Marshall — closed back cabinet ] [INFERRED]
  ◆ Configuration: 4x12 closed back
    └─ Tight, focused low end
          ↓
[ Shure SM57 — dynamic microphone ] [INFERRED]
  ◆ Placement: on-axis, edge of dust cap
    └─ Bright, present capture

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHY THIS CHAIN WORKS
Classic British rock crunch with a tube screamer for extra saturation.

CONFIDENCE: HIGH — well-documented tone.

TAGS
Characters: Distorted, Colored
Genres: Rock, Blues
</signal_chain>
"""


# ---------------------------------------------------------------------------
# parse_signal_chain_tags
# ---------------------------------------------------------------------------


class TestParseSignalChainTags:
    def test_extracts_characters_and_genres(self) -> None:
        tags = parse_signal_chain_tags(PHASE1_OUTPUT)
        assert "Distorted" in tags
        assert "Colored" in tags
        assert "Rock" in tags
        assert "Blues" in tags

    def test_no_duplicates(self) -> None:
        text = "TAGS\nCharacters: Clean, Clean\nGenres: Rock, Rock"
        tags = parse_signal_chain_tags(text)
        assert tags == ["Clean", "Rock"]

    def test_filters_invalid_tags(self) -> None:
        text = "TAGS\nCharacters: Clean, MadeUpTag\nGenres: Rock, NotAGenre"
        tags = parse_signal_chain_tags(text)
        assert tags == ["Clean", "Rock"]

    def test_empty_on_no_tags(self) -> None:
        tags = parse_signal_chain_tags("No tags section here")
        assert tags == []

    def test_multi_word_tags(self) -> None:
        text = "TAGS\nCharacters: Special FX, Mash-Up\nGenres: Funk & Soul, Hip Hop"
        tags = parse_signal_chain_tags(text)
        assert "Special FX" in tags
        assert "Mash-Up" in tags
        assert "Funk & Soul" in tags
        assert "Hip Hop" in tags

    def test_all_controlled_vocab_recognised(self) -> None:
        """Every tag in the controlled vocabulary is parseable."""
        chars = ", ".join(
            t for t in CONTROLLED_VOCAB if t in {"Clean", "Colored", "Distorted", "Spacious"}
        )
        genres = ", ".join(t for t in CONTROLLED_VOCAB if t in {"Rock", "Blues", "Metal", "Pop"})
        text = f"TAGS\nCharacters: {chars}\nGenres: {genres}"
        tags = parse_signal_chain_tags(text)
        assert len(tags) > 0
        assert all(t in CONTROLLED_VOCAB for t in tags)


# ---------------------------------------------------------------------------
# parse_signal_chain_components
# ---------------------------------------------------------------------------


class TestParseSignalChainComponents:
    def test_extracts_unit_names(self) -> None:
        components = parse_signal_chain_components(PHASE1_OUTPUT)
        assert "Tube Screamer" in components
        assert "Lead 800" in components
        assert "4x12 Marshall" in components
        assert "Shure SM57" in components

    def test_no_duplicates(self) -> None:
        text = "[ Lead 800 — tube amp ] [DOCUMENTED]\n[ Lead 800 — tube amp ] [INFERRED]\n"
        components = parse_signal_chain_components(text)
        assert components == ["Lead 800"]

    def test_empty_on_no_units(self) -> None:
        components = parse_signal_chain_components("No signal chain here")
        assert components == []

    def test_preserves_order(self) -> None:
        components = parse_signal_chain_components(PHASE1_OUTPUT)
        ts_idx = components.index("Tube Screamer")
        l800_idx = components.index("Lead 800")
        assert ts_idx < l800_idx


# ---------------------------------------------------------------------------
# score_exemplar
# ---------------------------------------------------------------------------


class TestScoreExemplar:
    def test_perfect_tag_match(self) -> None:
        record = {"tags": ["Distorted", "Rock"], "components": []}
        score = score_exemplar(
            record,
            query_tags=["Distorted", "Rock"],
            query_components=[],
            tag_weight=1.0,
            component_weight=0.0,
        )
        assert score == pytest.approx(1.0)

    def test_perfect_component_match(self) -> None:
        record = {
            "tags": [],
            "components": [
                {"component_name": "Lead 800"},
                {"component_name": "Tube Screamer"},
            ],
        }
        score = score_exemplar(
            record,
            query_tags=[],
            query_components=["Lead 800", "Tube Screamer"],
            tag_weight=0.0,
            component_weight=1.0,
        )
        assert score == pytest.approx(1.0)

    def test_zero_overlap(self) -> None:
        record = {"tags": ["Clean", "Pop"], "components": [{"component_name": "AC Box"}]}
        score = score_exemplar(
            record,
            query_tags=["Distorted", "Metal"],
            query_components=["Lead 800"],
            tag_weight=0.6,
            component_weight=0.4,
        )
        assert score == pytest.approx(0.0)

    def test_partial_tag_overlap(self) -> None:
        record = {"tags": ["Distorted", "Rock", "Amps & Cabinets"], "components": []}
        # "Amps & Cabinets" is not in controlled vocab → excluded
        # query has Distorted, Rock, Blues; exemplar has Distorted, Rock
        # Jaccard = 2 / 3 = 0.6667
        score = score_exemplar(
            record,
            query_tags=["Distorted", "Rock", "Blues"],
            query_components=[],
            tag_weight=1.0,
            component_weight=0.0,
        )
        assert score == pytest.approx(2 / 3, abs=0.001)

    def test_ignores_non_vocab_tags(self) -> None:
        """NI-internal tags like 'Guitar', 'Amps & Cabinets' are ignored."""
        record = {"tags": ["Distorted", "Guitar", "Amps & Cabinets"], "components": []}
        score = score_exemplar(
            record,
            query_tags=["Distorted"],
            query_components=[],
            tag_weight=1.0,
            component_weight=0.0,
        )
        assert score == pytest.approx(1.0)

    def test_empty_both(self) -> None:
        record: dict[str, list] = {"tags": [], "components": []}
        score = score_exemplar(record, [], [])
        assert score == pytest.approx(0.0)

    def test_weighted_combination(self) -> None:
        record = {
            "tags": ["Distorted", "Rock"],
            "components": [{"component_name": "Lead 800"}],
        }
        # Tags: Jaccard({Distorted, Rock}, {Distorted, Rock}) = 1.0
        # Components: overlap({Lead 800}, {Lead 800, Tube Screamer}) = 1/2 = 0.5
        score = score_exemplar(
            record,
            query_tags=["Distorted", "Rock"],
            query_components=["Lead 800", "Tube Screamer"],
            tag_weight=0.6,
            component_weight=0.4,
        )
        expected = 0.6 * 1.0 + 0.4 * 0.5
        assert score == pytest.approx(expected, abs=0.001)


# ---------------------------------------------------------------------------
# search_exemplars (integration — requires exemplar_store.json on disk)
# ---------------------------------------------------------------------------

_EXEMPLAR_STORE_PATH = DATA_PROCESSED / "exemplar_store.json"


@pytest.mark.skipif(
    not _EXEMPLAR_STORE_PATH.exists(),
    reason="exemplar_store.json not present in data/processed/",
)
class TestSearchExemplars:
    def test_returns_list(self) -> None:
        results = search_exemplars(PHASE1_OUTPUT, n_results=3)
        assert isinstance(results, list)
        assert len(results) <= 3

    def test_results_have_expected_keys(self) -> None:
        results = search_exemplars(PHASE1_OUTPUT, n_results=1)
        assert len(results) == 1
        r = results[0]
        assert "preset_name" in r
        assert "tags" in r
        assert "components" in r
        assert "distance" in r

    def test_distance_is_one_minus_score(self) -> None:
        results = search_exemplars(PHASE1_OUTPUT, n_results=5)
        for r in results:
            assert 0.0 <= r["distance"] <= 1.0

    def test_results_sorted_by_score_descending(self) -> None:
        results = search_exemplars(PHASE1_OUTPUT, n_results=10)
        distances = [r["distance"] for r in results]
        # distances are 1-score, so should be ascending (best match first)
        assert distances == sorted(distances)

    def test_deterministic_with_same_seed(self) -> None:
        r1 = search_exemplars(PHASE1_OUTPUT, n_results=5)
        r2 = search_exemplars(PHASE1_OUTPUT, n_results=5)
        assert [r["preset_name"] for r in r1] == [r["preset_name"] for r in r2]

    def test_pre_extracted_matches_raw_parsing(self) -> None:
        """Passing pre-extracted tags/components produces the same results as raw text."""
        tags = parse_signal_chain_tags(PHASE1_OUTPUT)
        components = parse_signal_chain_components(PHASE1_OUTPUT)
        r_raw = search_exemplars(PHASE1_OUTPUT, n_results=5)
        r_pre = search_exemplars(PHASE1_OUTPUT, n_results=5, tags=tags, components=components)
        assert [r["preset_name"] for r in r_raw] == [r["preset_name"] for r in r_pre]
        assert [r["distance"] for r in r_raw] == [r["distance"] for r in r_pre]

    def test_pre_extracted_tags_only(self) -> None:
        """Passing only tags still works; components fall back to regex parsing."""
        tags = parse_signal_chain_tags(PHASE1_OUTPUT)
        r_raw = search_exemplars(PHASE1_OUTPUT, n_results=3)
        r_pre = search_exemplars(PHASE1_OUTPUT, n_results=3, tags=tags)
        assert [r["preset_name"] for r in r_raw] == [r["preset_name"] for r in r_pre]

    def test_pre_extracted_components_only(self) -> None:
        """Passing only components still works; tags fall back to regex parsing."""
        components = parse_signal_chain_components(PHASE1_OUTPUT)
        r_raw = search_exemplars(PHASE1_OUTPUT, n_results=3)
        r_pre = search_exemplars(PHASE1_OUTPUT, n_results=3, components=components)
        assert [r["preset_name"] for r in r_raw] == [r["preset_name"] for r in r_pre]

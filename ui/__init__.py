# applied-skills: streamlit
"""ToneDef UI package — Streamlit rendering components and styles."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ui.components import (
    CONFIDENCE_DOT,
    EXAMPLE_QUERIES,
    MODIFICATION_COLOURS,
    render_component_card,
    render_guitar_tips,
    render_similar_presets,
    render_stepper,
    render_tone_overview,
)

__all__ = [
    "CONFIDENCE_DOT",
    "EXAMPLE_QUERIES",
    "MODIFICATION_COLOURS",
    "inject_css",
    "render_component_card",
    "render_guitar_tips",
    "render_similar_presets",
    "render_stepper",
    "render_tone_overview",
]

_CSS_PATH = Path(__file__).parent / "style.css"


@st.cache_data
def _load_css() -> str:
    return _CSS_PATH.read_text(encoding="utf-8")


def inject_css() -> None:
    """Read ``ui/style.css`` (cached) and inject it into the Streamlit page."""
    st.markdown(f"<style>{_load_css()}</style>", unsafe_allow_html=True)

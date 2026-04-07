# applied-skills: streamlit
"""ToneDef — single-page progressive app for Guitar Rig 7 preset generation."""

from __future__ import annotations

import contextlib
import html as html_mod

import anthropic
import streamlit as st
from ui import (
    EXAMPLE_QUERIES,
    inject_css,
    render_component_card,
    render_guitar_tips,
    render_similar_presets,
    render_stepper,
    render_tone_overview,
)

from tonedef.component_mapper import (
    load_amp_cabinet_lookup,
    load_annotations,
    load_schema,
    map_components,
)
from tonedef.log import configure_logging
from tonedef.models import ComponentOutput
from tonedef.pipeline import compose_query, generate_signal_chain
from tonedef.preset_builder import auto_preset_name, build_preset
from tonedef.settings import settings
from tonedef.signal_chain_parser import ParsedSignalChain, parse_signal_chain
from tonedef.tonal_vocab import get_all_selected_terms, get_ui_groups, load_descriptor_meta
from tonedef.validation import (
    validate_parameter_intent,
    validate_phase1,
    validate_phase2,
    validate_pre_build,
    validate_signal_chain_order,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

configure_logging()
st.set_page_config(page_title="ToneDef", page_icon="ui/assets/logo.png", layout="wide")

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

_DEFAULTS: dict[str, object] = {
    "query": "",
    "selected_modifiers": {},
    "signal_chain_raw": None,
    "signal_chain_parsed": None,
    "phase1_validation": None,
    "components": None,
    "exemplars": None,
    "preset_bytes": None,
    "preset_name": "ToneDef Preset",
    "processing": False,
    "_last_built_name": None,
}

for _key, _val in _DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = _val

# ---------------------------------------------------------------------------
# Cached resources
# ---------------------------------------------------------------------------


@st.cache_resource
def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_results() -> None:
    """Reset all generated state."""
    st.session_state.signal_chain_raw = None
    st.session_state.signal_chain_parsed = None
    st.session_state.phase1_validation = None
    st.session_state.components = None
    st.session_state.exemplars = None
    st.session_state.preset_bytes = None
    st.session_state.preset_name = "ToneDef Preset"
    st.session_state.pop("_last_built_name", None)
    st.session_state.selected_modifiers = {}


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

inject_css()

st.image("ui/assets/logo.png", width="stretch")
st.caption("Describe your tone → get a Guitar Rig 7 preset")

# Determine current stage
_has_results = st.session_state.components is not None
_stage = 2 if _has_results else (1 if st.session_state.processing else 0)
render_stepper(_stage)

# ---------------------------------------------------------------------------
# Results view — shown when we have components
# ---------------------------------------------------------------------------

if _has_results:
    parsed: ParsedSignalChain = st.session_state.signal_chain_parsed

    # Query summary bar
    query_text = html_mod.escape(st.session_state.query)
    modifiers = get_all_selected_terms(st.session_state.selected_modifiers)
    mods_html = (
        "".join(f'<span class="qs-mod">{html_mod.escape(m)}</span>' for m in modifiers)
        if modifiers
        else ""
    )

    st.markdown(
        f'<div class="query-summary">'
        f'<span class="qs-text">🎸 {query_text}</span>'
        f'<span class="qs-mods">{mods_html}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )

    col_edit, col_clear = st.columns([1, 1])
    with col_edit:
        if st.button("✏️  Edit description", use_container_width=True):
            st.session_state.components = None
            st.session_state.preset_bytes = None
            st.rerun()
    with col_clear:
        if st.button("🔄  Start over", use_container_width=True):
            _clear_results()
            st.session_state.query = ""
            st.rerun()

    # Tone overview (from Phase 1)
    render_tone_overview(parsed)

    # Guitar & Playing Tips
    render_guitar_tips(parsed)

    # Phase 1 validation
    p1v = st.session_state.phase1_validation
    if p1v is not None:
        for e in p1v.errors:
            st.error(e, icon="❌")
        for w in p1v.warnings:
            st.warning(w, icon="⚠️")

    # Phase 2 validation
    _build_comps = st.session_state.components
    if _build_comps:
        _validated = []
        for _c in _build_comps:
            with contextlib.suppress(Exception):
                _validated.append(ComponentOutput.model_validate(_c))
        if _validated:
            _schema = load_schema()
            _annotations = load_annotations()
            _p2v = validate_phase2(_validated, _schema)
            _order_v = validate_signal_chain_order(_validated, load_amp_cabinet_lookup())
            _pre_v = validate_pre_build(_validated)
            _intent_v = validate_parameter_intent(
                _validated,
                _annotations,
                st.session_state.signal_chain_raw or "",
            )
            _all_v = _p2v.merge(_order_v).merge(_pre_v).merge(_intent_v)
            for _e in _all_v.errors:
                st.error(_e, icon="❌")
            for _w in _all_v.warnings:
                st.warning(_w, icon="⚠️")

    # Similar presets analysed
    render_similar_presets(st.session_state.exemplars)

    # Component cards
    st.markdown("##### Signal Chain Components")
    _card_schema = load_schema()
    for i, comp in enumerate(st.session_state.components):
        render_component_card(comp, schema=_card_schema)
        if i < len(st.session_state.components) - 1:
            st.caption("↓")

    # Raw output
    with st.expander("🔍 Raw signal chain output"):
        st.code(st.session_state.signal_chain_raw, language=None)

    # Download section
    st.markdown("##### Download Preset")

    preset_name = st.text_input(
        "Preset name",
        value=st.session_state.preset_name,
        max_chars=64,
    )
    st.session_state.preset_name = preset_name

    if st.session_state.preset_bytes is None or preset_name != st.session_state.get(
        "_last_built_name"
    ):
        with st.spinner("Building preset file..."):
            st.session_state.preset_bytes = build_preset(st.session_state.components, preset_name)
            st.session_state["_last_built_name"] = preset_name

    safe_name = (
        "".join(c if c.isalnum() or c in (" ", "-", "_") else "" for c in preset_name).strip()
        or "tonedef_preset"
    )

    st.download_button(
        label="⬇️  Download preset",
        data=st.session_state.preset_bytes,
        file_name=f"{safe_name}.ngrr",
        mime="application/octet-stream",
        type="primary",
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Processing view — shown briefly while building
# ---------------------------------------------------------------------------

elif st.session_state.processing:
    with st.status("Building your tone...", expanded=True) as status:
        client = get_client()

        st.write("🔍 Analysing tone description...")
        modifiers = get_all_selected_terms(st.session_state.selected_modifiers)
        composed = compose_query(st.session_state.query, modifiers)
        raw = generate_signal_chain(composed, client)
        st.session_state.signal_chain_raw = raw
        parsed_result = parse_signal_chain(raw)
        st.session_state.signal_chain_parsed = parsed_result
        st.session_state.phase1_validation = validate_phase1(parsed_result)

        st.write("🔧 Mapping to Guitar Rig 7 components...")
        components, exemplars = map_components(raw, parsed_result, client)
        st.session_state.components = components
        st.session_state.exemplars = exemplars

        st.write("📦 Preparing preset...")
        name = auto_preset_name(st.session_state.query)
        st.session_state.preset_name = name
        st.session_state.preset_bytes = build_preset(components, name)
        st.session_state["_last_built_name"] = name

        st.session_state.processing = False
        status.update(label="Done!", state="complete")

    st.rerun()

# ---------------------------------------------------------------------------
# Describe view — input form
# ---------------------------------------------------------------------------

else:
    query = st.text_area(
        "Your tone description",
        value=st.session_state.query,
        placeholder="e.g. warm singing sustain with a slight chorus shimmer",
        height=120,
        label_visibility="collapsed",
    )

    st.markdown("###### Try an example")
    cols = st.columns(3)
    for i, example in enumerate(EXAMPLE_QUERIES):
        with cols[i % 3]:
            if st.button(example, key=f"ex_{i}", use_container_width=True):
                _clear_results()
                st.session_state.selected_modifiers = {}
                st.session_state.query = example
                st.session_state.processing = True
                st.rerun()

    # -------------------------------------------------------------------
    # Tonal modifier chips — grouped by zone then sub-group
    # -------------------------------------------------------------------

    st.markdown("")  # spacer
    st.markdown("###### Refine your tone *(optional)*")

    _meta = load_descriptor_meta()
    _zone_order = ("pre_amp", "amp", "cabinet", "room_mic", "post_cab")
    _zone_info = _meta.get("zones", {})

    sel: dict[str, str | None] = st.session_state.selected_modifiers

    for zone in _zone_order:
        z_meta = _zone_info.get(zone, {})
        z_label = f"{z_meta.get('icon', '')} {z_meta.get('label', zone)}"
        groups = get_ui_groups(zone)
        if not groups:
            continue

        with st.expander(z_label):
            for grp in groups:
                grp_key = f"{zone}__{grp['group']}"
                current = sel.get(grp_key)

                options_list = [opt["ui_label"] for opt in grp["options"]]
                term_by_label = {opt["ui_label"]: opt["term"] for opt in grp["options"]}
                label_by_term = {opt["term"]: opt["ui_label"] for opt in grp["options"]}

                default_label = label_by_term.get(current) if current else None

                st.caption(grp["description"])
                pill_col, help_col = st.columns([6, 1])
                with pill_col:
                    chosen_label = st.pills(
                        grp["group"],
                        options_list,
                        default=default_label,
                        selection_mode="single",
                        key=f"pills_{grp_key}",
                    )
                with help_col, st.popover("ℹ️"):  # noqa: RUF001
                    for opt in grp["options"]:
                        st.markdown(f"- **{opt['ui_label']}** — {opt['ui_description']}")

                sel[grp_key] = term_by_label.get(chosen_label) if chosen_label else None  # type: ignore[arg-type]

    st.session_state.selected_modifiers = sel

    # Active modifiers summary
    selected_terms = get_all_selected_terms(sel)
    if selected_terms:
        pills_md = "  ".join(f"`{t}`" for t in selected_terms)
        st.markdown(f"**Active modifiers:** {pills_md}")

    st.markdown("")  # spacer

    if st.button(
        "🎸  Build My Tone",
        type="primary",
        disabled=not query,
        use_container_width=True,
    ):
        _clear_results()
        st.session_state.query = query
        st.session_state.processing = True
        st.rerun()

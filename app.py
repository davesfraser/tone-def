# applied-skills: streamlit
"""ToneDef — sidebar-navigation app with progressive page unlock."""

from __future__ import annotations

import contextlib
import tempfile
from pathlib import Path

import anthropic
import streamlit as st

from tonedef.component_mapper import load_amp_cabinet_lookup, load_schema, map_components
from tonedef.models import ComponentOutput
from tonedef.ngrr_builder import transplant_preset
from tonedef.paths import DATA_EXTERNAL
from tonedef.pipeline import compose_query, generate_signal_chain
from tonedef.settings import settings
from tonedef.signal_chain_parser import ParsedSignalChain, parse_signal_chain
from tonedef.tonal_vocab import get_all_selected_terms, get_ui_groups, load_descriptor_meta
from tonedef.validation import (
    validate_phase1,
    validate_phase2,
    validate_pre_build,
    validate_signal_chain_order,
)
from tonedef.xml_builder import build_signal_chain_xml

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="ToneDef", page_icon="🎸", layout="wide")

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

_DEFAULTS: dict[str, object] = {
    "page": "describe",
    "query": "",
    "selected_modifiers": {},
    "signal_chain_raw": None,
    "signal_chain_parsed": None,
    "phase1_validation": None,
    "components": None,
    "preset_bytes": None,
    "preset_name": "ToneDef Preset",
    "analysing": False,
    "building": False,
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
# Constants
# ---------------------------------------------------------------------------

_PROVENANCE_COLOURS = {
    "DOCUMENTED": "#4CAF50",
    "INFERRED": "#FF9800",
    "ESTIMATED": "#F44336",
}

_CONFIDENCE_COLOURS = {
    "HIGH": "green",
    "MEDIUM": "orange",
    "LOW": "red",
}

_EXAMPLE_QUERIES = [
    "Hotel California solo tone",
    "Jimi Hendrix — Purple Haze rhythm",
    "Clean jazzy tone with warm reverb",
    "Shoegaze wall-of-sound like My Bloody Valentine",
    "80s new wave jangly clean tone",
    "High gain djent tone, tight and percussive",
]

# Section grouping for analysis tabs
_PEDALS_AMP_TITLES = {"Signal Chain", "Guitar Signal Chain"}
_CAB_MIC_TITLES = {"Cabinet And Mic"}
_POST_TITLES = {"Recording Chain", "Studio Processing"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_results() -> None:
    """Reset all generated state."""
    st.session_state.signal_chain_raw = None
    st.session_state.signal_chain_parsed = None
    st.session_state.phase1_validation = None
    st.session_state.components = None
    st.session_state.preset_bytes = None
    st.session_state.preset_name = "ToneDef Preset"
    st.session_state.pop("_last_built_name", None)
    st.session_state.selected_modifiers = {}


def _render_unit_card(unit) -> None:  # noqa: ANN001
    """Render a single gear unit as a styled card."""
    colour = _PROVENANCE_COLOURS.get(unit.provenance, "#888")
    gr_note = f"  ·  *Guitar Rig → {unit.gr_equivalent}*" if unit.gr_equivalent else ""

    st.markdown(f"**{unit.name}** — {unit.unit_type}&ensp;:{colour}[{unit.provenance}]{gr_note}")

    if unit.parameters:
        for p in unit.parameters:
            expl = f"  \n*{p.explanation}*" if p.explanation else ""
            st.markdown(f"&ensp;&ensp;◆ **{p.name}:** {p.value}{expl}")


def _render_section_units(parsed: ParsedSignalChain, title_set: set[str]) -> None:
    """Render units from all sections whose title is in *title_set*."""
    for section in parsed.sections:
        if section.title in title_set:
            if len([s for s in parsed.sections if s.title in title_set]) > 1:
                st.markdown(f"##### {section.title}")
            for j, unit in enumerate(section.units):
                _render_unit_card(unit)
                if j < len(section.units) - 1:
                    st.markdown(
                        "<div style='text-align:center;color:#555;font-size:1.2em'>↓</div>",
                        unsafe_allow_html=True,
                    )


def _build_preset(components: list[dict], name: str) -> bytes:
    """Build a .ngrr file from components and return the bytes."""
    schema = load_schema()
    xml = build_signal_chain_xml(components, schema)

    with tempfile.NamedTemporaryFile(suffix=".ngrr", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    transplant_preset(
        template_path=DATA_EXTERNAL / "Blank_template.ngrr",
        signal_chain_xml=xml,
        output_path=tmp_path,
        preset_name=name,
    )
    data = tmp_path.read_bytes()
    tmp_path.unlink()
    return data


def _nav_options() -> list[str]:
    """Return the list of unlocked page labels."""
    pages = ["🎸  Describe your tone"]
    if st.session_state.signal_chain_parsed is not None:
        pages.append("🔍  Tonal Analysis")
    if st.session_state.components is not None:
        pages.append("🔧  Preset Build")
    return pages


_PAGE_KEYS = {
    "🎸  Describe your tone": "describe",
    "🔍  Tonal Analysis": "analysis",
    "🔧  Preset Build": "build",
}

# ---------------------------------------------------------------------------
# Sidebar — navigation only
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🎸 ToneDef")
    st.caption("Describe your tone, get a Guitar Rig 7 preset")

    options = _nav_options()
    # Map current page key back to the label for the radio default
    current_label = next(
        (label for label, key in _PAGE_KEYS.items() if key == st.session_state.page), options[0]
    )
    # Clamp to available options
    if current_label not in options:
        current_label = options[-1]

    choice = st.radio(
        "Navigate",
        options,
        index=options.index(current_label),
        label_visibility="collapsed",
    )
    st.session_state.page = _PAGE_KEYS[choice]

    if st.session_state.signal_chain_raw is not None:
        st.divider()
        if st.button("🔄  Start over", use_container_width=True):
            _clear_results()
            st.session_state.selected_modifiers = {}
            st.session_state.query = ""
            st.session_state.page = "describe"
            st.rerun()

# ---------------------------------------------------------------------------
# Page: Describe your tone
# ---------------------------------------------------------------------------

if st.session_state.page == "describe":
    st.header("Describe your tone")
    st.markdown(
        "Tell us the sound you're after — reference a song, artist, genre, "
        "or just describe the vibe. We'll turn it into a Guitar Rig 7 preset."
    )

    query = st.text_area(
        "Your tone description",
        value=st.session_state.query,
        placeholder="e.g. warm singing sustain with a slight chorus shimmer",
        height=120,
        label_visibility="collapsed",
    )

    st.markdown("###### Try an example")
    cols = st.columns(3)
    for i, example in enumerate(_EXAMPLE_QUERIES):
        with cols[i % 3]:
            if st.button(example, key=f"ex_{i}", use_container_width=True):
                _clear_results()
                st.session_state.selected_modifiers = {}
                st.session_state.query = example
                st.session_state.analysing = True
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
                # Determine current selection
                current = sel.get(grp_key)

                # Build options list
                options_list = [opt["ui_label"] for opt in grp["options"]]
                term_by_label = {opt["ui_label"]: opt["term"] for opt in grp["options"]}
                label_by_term = {opt["term"]: opt["ui_label"] for opt in grp["options"]}

                # Pre-select the currently stored label (or None)
                default_label = label_by_term.get(current) if current else None

                header_col, help_col = st.columns([6, 1])
                with header_col:
                    chosen_label = st.pills(
                        grp["group"],
                        options_list,
                        default=default_label,
                        selection_mode="single",
                        key=f"pills_{grp_key}",
                    )
                with help_col, st.popover("ℹ️"):  # noqa: RUF001
                    st.markdown(f"**{grp['group']}** — {grp['description']}")
                    for opt in grp["options"]:
                        st.markdown(f"- **{opt['ui_label']}** — {opt['ui_description']}")

                # Write the term (not label) back to session state
                sel[grp_key] = term_by_label.get(chosen_label) if chosen_label else None  # type: ignore[arg-type]

    st.session_state.selected_modifiers = sel

    # Show active modifiers summary
    selected_terms = get_all_selected_terms(sel)
    if selected_terms:
        pills_md = "  ".join(f"`{t}`" for t in selected_terms)
        st.markdown(f"**Active modifiers:** {pills_md}")

    st.markdown("")  # spacer

    if st.button(
        "🔍  Analyse Tone",
        type="primary",
        disabled=not query,
        use_container_width=True,
    ):
        _clear_results()
        st.session_state.query = query
        st.session_state.analysing = True
        st.rerun()

    if st.session_state.analysing:
        with st.spinner("Analysing tone..."):
            client = get_client()
            modifiers = get_all_selected_terms(st.session_state.selected_modifiers)
            composed = compose_query(st.session_state.query, modifiers)
            raw = generate_signal_chain(composed, client)
            st.session_state.signal_chain_raw = raw
            parsed = parse_signal_chain(raw)
            st.session_state.signal_chain_parsed = parsed
            st.session_state.phase1_validation = validate_phase1(parsed)
            st.session_state.analysing = False
            st.session_state.page = "analysis"
            st.rerun()

# ---------------------------------------------------------------------------
# Page: Tonal Analysis
# ---------------------------------------------------------------------------

elif st.session_state.page == "analysis":
    parsed: ParsedSignalChain = st.session_state.signal_chain_parsed

    # Header
    st.header("Tonal Analysis")

    ct_label = parsed.chain_type.replace("_", " ")
    ct_colour = "blue" if parsed.chain_type == "FULL_PRODUCTION" else "violet"
    header_parts = [f":{ct_colour}[**{ct_label}**] — {parsed.chain_type_reason}"]

    if parsed.confidence:
        conf_colour = _CONFIDENCE_COLOURS.get(parsed.confidence, "gray")
        header_parts.append(
            f"Confidence: :{conf_colour}[**{parsed.confidence}**] — {parsed.confidence_detail}"
        )

    st.markdown("  \n".join(header_parts))

    if parsed.tags_characters or parsed.tags_genres:
        tag_parts = [f":orange[{t}]" for t in parsed.tags_characters]
        tag_parts += [f":blue[{t}]" for t in parsed.tags_genres]
        st.markdown(" ".join(tag_parts))

    # Grouped tabs
    tab_labels: list[str] = []
    tab_groups: list[set[str]] = []

    pedal_sections = [s for s in parsed.sections if s.title in _PEDALS_AMP_TITLES]
    cab_sections = [s for s in parsed.sections if s.title in _CAB_MIC_TITLES]
    post_sections = [s for s in parsed.sections if s.title in _POST_TITLES]

    if pedal_sections:
        tab_labels.append("Pedals & Amp")
        tab_groups.append(_PEDALS_AMP_TITLES)
    if cab_sections:
        tab_labels.append("Cabinet & Mic")
        tab_groups.append(_CAB_MIC_TITLES)
    if post_sections:
        tab_labels.append("Post-Processing")
        tab_groups.append(_POST_TITLES)

    if tab_labels:
        tabs = st.tabs(tab_labels)
        for tab, group in zip(tabs, tab_groups, strict=False):
            with tab:
                _render_section_units(parsed, group)

    # Insights
    col_why, col_notes = st.columns(2)
    with col_why:
        if parsed.why_it_works:
            st.info(f"**Why this chain works**\n\n{parsed.why_it_works}", icon="💡")
    with col_notes:
        if parsed.playing_notes:
            st.warning(f"**Playing notes**\n\n{parsed.playing_notes}", icon="🎵")

    # Raw output
    with st.expander("Raw signal chain output"):
        st.code(st.session_state.signal_chain_raw, language=None)

    # Phase 1 validation
    p1v = st.session_state.phase1_validation
    if p1v is not None:
        for e in p1v.errors:
            st.error(e, icon="✗")
        for w in p1v.warnings:
            st.warning(w, icon="⚠️")

    st.markdown("")  # spacer

    build_blocked = p1v is not None and not p1v.is_valid
    if st.button(
        "🔧  Build Preset",
        type="primary",
        use_container_width=True,
        disabled=build_blocked,
    ):
        st.session_state.building = True
        st.rerun()

    if st.session_state.building:
        with st.spinner("Mapping to Guitar Rig 7 components..."):
            client = get_client()
            components = map_components(
                st.session_state.signal_chain_raw,
                st.session_state.signal_chain_parsed,
                client,
            )
            st.session_state.components = components
            st.session_state.building = False
            st.session_state.page = "build"
            st.rerun()

# ---------------------------------------------------------------------------
# Page: Preset Build
# ---------------------------------------------------------------------------

elif st.session_state.page == "build":
    st.header("Preset Build")
    st.markdown("Your signal chain mapped to Guitar Rig 7 components.")

    # Phase 2 validation
    _build_comps = st.session_state.components
    if _build_comps:
        _validated = []
        for _c in _build_comps:
            with contextlib.suppress(Exception):
                _validated.append(ComponentOutput.model_validate(_c))
        if _validated:
            _schema = load_schema()
            _p2v = validate_phase2(_validated, _schema)
            _order_v = validate_signal_chain_order(_validated, load_amp_cabinet_lookup())
            _pre_v = validate_pre_build(_validated)
            _all_v = _p2v.merge(_order_v).merge(_pre_v)
            for _e in _all_v.errors:
                st.error(_e, icon="✗")
            for _w in _all_v.warnings:
                st.warning(_w, icon="⚠️")

    for comp in st.session_state.components:
        mod = comp.get("modification", "—")
        base = comp.get("base_exemplar", "")
        conf = comp.get("confidence", "")
        mod_colour = {
            "unchanged": "green",
            "adjusted": "orange",
            "swapped": "red",
            "added": "violet",
        }.get(mod, "gray")

        origin = f"  ·  *from {base}*" if base else ""
        st.markdown(
            f"**{comp['component_name']}** (`{comp['component_id']}`)"
            f"  ·  :{mod_colour}[{mod}]"
            f"  ·  {conf}"
            f"{origin}"
        )

        # Show parameter details if available
        params = comp.get("parameters", {})
        if params:
            param_strs = [f"**{k}:** {v}" for k, v in params.items()]
            st.caption("&ensp;&ensp;".join(param_strs))

    st.divider()

    preset_name = st.text_input(
        "Preset name",
        value=st.session_state.preset_name,
        max_chars=64,
    )
    st.session_state.preset_name = preset_name

    # Build .ngrr on demand
    if st.session_state.preset_bytes is None or preset_name != st.session_state.get(
        "_last_built_name"
    ):
        with st.spinner("Building .ngrr..."):
            st.session_state.preset_bytes = _build_preset(st.session_state.components, preset_name)
            st.session_state["_last_built_name"] = preset_name

    safe_name = (
        "".join(c if c.isalnum() or c in (" ", "-", "_") else "" for c in preset_name).strip()
        or "tonedef_preset"
    )

    st.download_button(
        label="⬇️  Download .ngrr",
        data=st.session_state.preset_bytes,
        file_name=f"{safe_name}.ngrr",
        mime="application/octet-stream",
        type="primary",
        use_container_width=True,
    )

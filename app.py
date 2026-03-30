# applied-skills: streamlit
"""ToneDef — single-page progressive app for Guitar Rig 7 preset generation."""

from __future__ import annotations

import contextlib
import html as html_mod
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
# Constants
# ---------------------------------------------------------------------------

_MODIFICATION_COLOURS = {
    "unchanged": "#4CAF50",
    "adjusted": "#FF9800",
    "swapped": "#F44336",
    "added": "#9C27B0",
}

_CHAIN_TYPE_LABELS = {
    "FULL_PRODUCTION": "Full Production Chain",
    "AMP_ONLY": "Amplifier-Focused Chain",
}

_CONFIDENCE_DOT = {
    "documented": "🟢",
    "inferred": "🟡",
    "estimated": "🔴",
}

_EXAMPLE_QUERIES = [
    "Jimi Hendrix — Purple Haze rhythm",
    "Pink Floyd — Comfortably Numb solo",
    "Clean jazzy tone with warm reverb",
    "Shoegaze wall-of-sound like My Bloody Valentine",
    "80s new wave jangly clean tone",
    "High gain djent tone, tight and percussive",
]

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Global ── */
.block-container { max-width: 860px; }
section[data-testid="stSidebar"] { display: none; }

/* ── Stepper bar ── */
.stepper {
    display: flex; align-items: center; justify-content: center;
    gap: 0; margin: 0.5rem auto 1.5rem; padding: 0.6rem 1rem;
    background: #1A1D23; border-radius: 12px; border: 1px solid #2a2d35;
}
.step {
    display: flex; align-items: center; gap: 0.45rem;
    font-size: 0.82rem; font-weight: 500; color: #555;
    font-family: 'Inter', sans-serif;
}
.step.active { color: #FF6B35; }
.step.done { color: #4CAF50; }
.step-arrow { color: #333; margin: 0 0.5rem; font-size: 0.75rem; }

/* ── Cards ── */
.tone-card {
    background: #1A1D23; border: 1px solid #2a2d35; border-radius: 12px;
    padding: 1.2rem 1.4rem; margin-bottom: 1rem;
}
.tone-card h4 {
    margin: 0 0 0.5rem 0; font-family: 'Inter', sans-serif; font-size: 1rem;
}
.tone-card p { margin: 0.3rem 0; color: #ccc; font-size: 0.92rem; line-height: 1.5; }

/* ── Component cards ── */
.comp-card {
    background: #1A1D23; border: 1px solid #2a2d35; border-radius: 12px;
    padding: 1rem 1.2rem; margin-bottom: 0.75rem;
}
.comp-header {
    display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.4rem;
    flex-wrap: wrap;
}
.comp-name {
    font-family: 'Inter', sans-serif; font-weight: 600; font-size: 1rem;
    color: #FAFAFA;
}
.comp-pill {
    display: inline-block; padding: 0.15rem 0.55rem; border-radius: 20px;
    font-size: 0.72rem; font-weight: 600; color: #fff;
    text-transform: uppercase; letter-spacing: 0.03em;
}
.comp-rationale {
    color: #bbb; font-size: 0.88rem; line-height: 1.55; margin: 0.4rem 0 0 0;
    font-family: 'Inter', sans-serif;
}
.comp-params {
    margin-top: 0.6rem; padding: 0.5rem 0.7rem;
    background: #12141a; border-radius: 8px;
    font-family: 'JetBrains Mono', monospace; font-size: 0.78rem;
    color: #888; line-height: 1.7;
}
.comp-params span.pk { color: #FF6B35; }
.comp-params span.pv { color: #aaa; }

/* ── Query summary bar ── */
.query-summary {
    background: #1A1D23; border: 1px solid #2a2d35; border-radius: 10px;
    padding: 0.8rem 1.2rem; margin-bottom: 1rem;
    display: flex; align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 0.5rem;
}
.query-summary .qs-text {
    color: #ccc; font-size: 0.9rem; font-family: 'Inter', sans-serif;
    flex: 1;
}
.query-summary .qs-mods {
    display: flex; gap: 0.3rem; flex-wrap: wrap;
}
.query-summary .qs-mod {
    background: #FF6B3522; color: #FF6B35; font-size: 0.72rem;
    padding: 0.1rem 0.45rem; border-radius: 10px; font-weight: 500;
}

/* ── Section dividers ── */
.section-label {
    font-size: 0.7rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.08em; color: #555; margin: 1.2rem 0 0.6rem 0;
    font-family: 'Inter', sans-serif;
}
.chain-arrow {
    text-align: center; color: #444; font-size: 1rem; margin: 0.15rem 0;
}

/* ── Example buttons equal height ── */
div[data-testid="column"] .stButton {
    height: 100%;
}
div[data-testid="column"] .stButton > button {
    height: 100% !important;
    min-height: 2.8rem;
}

/* ── Tag bar ── */
.tag-bar {
    display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;
    margin-bottom: 0.6rem; font-family: 'Inter', sans-serif; font-size: 0.85rem;
}
.tag-bar .tag-label {
    color: #888; font-weight: 500; font-size: 0.75rem;
    text-transform: uppercase; letter-spacing: 0.04em;
}
.tag-bar .tag-pill {
    display: inline-block; padding: 0.15rem 0.55rem; border-radius: 20px;
    font-size: 0.75rem; font-weight: 500;
}
.tag-pill.genre { background: #2196F322; color: #64B5F6; }
.tag-pill.character { background: #FF980022; color: #FFB74D; }
.tag-pill.chain-type { background: #4CAF5022; color: #81C784; }

/* ── Component description ── */
.comp-description {
    color: #999; font-size: 0.82rem; line-height: 1.4; margin: 0.1rem 0 0.3rem 0;
    font-family: 'Inter', sans-serif; font-style: italic;
}
</style>
"""


def _inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Stepper
# ---------------------------------------------------------------------------


def _render_stepper(stage: int) -> None:
    """Render a visual progress stepper. stage: 0=describe, 1=processing, 2=results."""
    labels = ["Describe", "Analyse & Build", "Results"]
    parts: list[str] = []
    for i, label in enumerate(labels):
        if i < stage:
            cls = "done"
        elif i == stage:
            cls = "active"
        else:
            cls = ""
        parts.append(f'<span class="step {cls}">{"✓ " if i < stage else ""}{label}</span>')
        if i < len(labels) - 1:
            parts.append('<span class="step-arrow">▸</span>')
    st.markdown(f'<div class="stepper">{"".join(parts)}</div>', unsafe_allow_html=True)


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


def _auto_preset_name(query: str) -> str:
    """Generate a clean preset name from the query text."""
    name = query.strip()[:50]
    for prefix in ("I want ", "i want ", "Give me ", "give me "):
        if name.startswith(prefix):
            name = name[len(prefix) :]
    return name.strip().title() if name else "ToneDef Preset"


def _render_component_card(comp: dict, schema: dict | None = None) -> None:
    """Render a single component as a styled card with human-readable params."""
    name = html_mod.escape(comp.get("component_name", ""))
    mod = html_mod.escape(comp.get("modification", "—"))
    conf = html_mod.escape(comp.get("confidence", ""))
    rationale = html_mod.escape(comp.get("rationale", ""))
    description = html_mod.escape(comp.get("description", ""))
    params = comp.get("parameters", {})
    base = html_mod.escape(comp.get("base_exemplar", ""))

    mod_colour = _MODIFICATION_COLOURS.get(mod, "#666")
    conf_dot = _CONFIDENCE_DOT.get(conf, "⚪")

    # Build param_id → param_name lookup from schema
    param_names: dict[str, str] = {}
    if schema and name in schema:
        for p in schema[name].get("parameters", []):
            param_names[p["param_id"]] = p.get("param_name", p["param_id"])

    # Integer enum params that should be displayed as-is (not on 0-10 scale)
    _INT_ENUM_PREFIXES = ("Cab", "Mic", "MPos")

    param_pairs: list[str] = []
    for k, v in params.items():
        if k == "Pwr":
            continue
        display_name = html_mod.escape(param_names.get(k, k))
        # Format value: int enums as-is, 0.0→Off, 1.0→Full for switches, else 0-10 scale
        if any(k.startswith(p) for p in _INT_ENUM_PREFIXES):
            display_val = str(int(v)) if isinstance(v, float) and v == int(v) else str(v)
        elif isinstance(v, (int, float)):
            if v == 0.0:
                display_val = "Off"
            elif v == 1.0 and display_name in ("On/Off", "Power", "Bright"):
                display_val = "On"
            else:
                display_val = f"{round(float(v) * 10, 1):.1f}/10"
                # Clean up ".0" for whole numbers
                if display_val.endswith(".0/10"):
                    display_val = f"{round(float(v) * 10)}/10"
        else:
            display_val = str(v)
        param_pairs.append(
            f'<span class="pk">{display_name}</span>: <span class="pv">{html_mod.escape(display_val)}</span>'
        )
    params_html = " &nbsp;·&nbsp; ".join(param_pairs) if param_pairs else ""

    origin = f' <span style="color:#666;font-size:0.78rem">from {base}</span>' if base else ""

    card_html = f"""<div class="comp-card">
  <div class="comp-header">
    <span class="comp-name">{name}</span>
    <span class="comp-pill" style="background:{mod_colour}">{mod}</span>
    <span style="font-size:0.75rem" title="{conf}">{conf_dot}</span>
    {origin}
  </div>"""

    if description:
        card_html += f'\n  <p class="comp-description">{description}</p>'

    if rationale:
        card_html += f'\n  <p class="comp-rationale">{rationale}</p>'

    if params_html:
        card_html += f'\n  <div class="comp-params">{params_html}</div>'

    card_html += "\n</div>"
    st.markdown(card_html, unsafe_allow_html=True)


def _render_similar_presets(exemplars: list[dict] | None) -> None:
    """Render a collapsible section showing similar factory presets analysed."""
    if not exemplars:
        return
    with st.expander("🔎 Similar Guitar Rig presets analysed"):
        for ex in exemplars:
            preset_name = html_mod.escape(ex.get("preset_name", ex.get("name", "Unknown")))
            tags = ex.get("tags", [])
            tag_str = ", ".join(html_mod.escape(t) for t in tags) if tags else "no tags"
            comp_count = len(ex.get("components", []))
            st.markdown(f"**{preset_name}** — {tag_str} · {comp_count} components")


def _render_tone_overview(parsed: ParsedSignalChain) -> None:
    """Render the tone overview: tag bar + About Your Tone card."""
    ct_label = _CHAIN_TYPE_LABELS.get(parsed.chain_type, parsed.chain_type.replace("_", " "))

    # Tag bar with styled pills
    tag_pills = [f'<span class="tag-pill chain-type">{html_mod.escape(ct_label)}</span>']
    if parsed.tags_genres:
        tag_pills.append('<span class="tag-label">Genre</span>')
        tag_pills.extend(
            f'<span class="tag-pill genre">{html_mod.escape(t)}</span>' for t in parsed.tags_genres
        )
    if parsed.tags_characters:
        tag_pills.append('<span class="tag-label">Character</span>')
        tag_pills.extend(
            f'<span class="tag-pill character">{html_mod.escape(t)}</span>'
            for t in parsed.tags_characters
        )
    st.markdown(f'<div class="tag-bar">{" ".join(tag_pills)}</div>', unsafe_allow_html=True)

    # About Your Tone — full-width narrative card
    about_parts: list[str] = []
    if parsed.chain_type_reason:
        about_parts.append(html_mod.escape(parsed.chain_type_reason.rstrip(".")) + ".")
    if parsed.why_it_works:
        about_parts.append(html_mod.escape(parsed.why_it_works))
    if about_parts:
        about_text = " ".join(about_parts)
        st.markdown(
            f'<div class="tone-card"><h4>💡 About Your Tone</h4><p>{about_text}</p></div>',
            unsafe_allow_html=True,
        )


def _render_guitar_tips(parsed: ParsedSignalChain) -> None:
    """Render the guitar & playing tips card from Phase 1 playing_notes."""
    if parsed.playing_notes:
        st.markdown(
            f'<div class="tone-card"><h4>🎸 Guitar & Playing Tips</h4>'
            f"<p>{html_mod.escape(parsed.playing_notes)}</p></div>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

_inject_css()

st.markdown("# 🎸 ToneDef")
st.caption("Describe your tone → get a Guitar Rig 7 preset")

# Determine current stage
_has_results = st.session_state.components is not None
_stage = 2 if _has_results else (1 if st.session_state.processing else 0)
_render_stepper(_stage)

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
    _render_tone_overview(parsed)

    # Guitar & Playing Tips
    _render_guitar_tips(parsed)

    # Phase 1 validation
    p1v = st.session_state.phase1_validation
    if p1v is not None:
        for e in p1v.errors:
            st.error(e, icon="✗")
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
            _p2v = validate_phase2(_validated, _schema)
            _order_v = validate_signal_chain_order(_validated, load_amp_cabinet_lookup())
            _pre_v = validate_pre_build(_validated)
            _all_v = _p2v.merge(_order_v).merge(_pre_v)
            for _e in _all_v.errors:
                st.error(_e, icon="✗")
            for _w in _all_v.warnings:
                st.warning(_w, icon="⚠️")

    # Similar presets analysed
    _render_similar_presets(st.session_state.exemplars)

    # Component cards
    st.markdown('<div class="section-label">Signal Chain Components</div>', unsafe_allow_html=True)
    _card_schema = load_schema()
    for i, comp in enumerate(st.session_state.components):
        _render_component_card(comp, schema=_card_schema)
        if i < len(st.session_state.components) - 1:
            st.markdown('<div class="chain-arrow">↓</div>', unsafe_allow_html=True)

    # Raw output
    with st.expander("🔍 Raw signal chain output"):
        st.code(st.session_state.signal_chain_raw, language=None)

    # Download section
    st.markdown('<div class="section-label">Download Preset</div>', unsafe_allow_html=True)

    preset_name = st.text_input(
        "Preset name",
        value=st.session_state.preset_name,
        max_chars=64,
    )
    st.session_state.preset_name = preset_name

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
        name = _auto_preset_name(st.session_state.query)
        st.session_state.preset_name = name
        st.session_state.preset_bytes = _build_preset(components, name)
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
    for i, example in enumerate(_EXAMPLE_QUERIES):
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

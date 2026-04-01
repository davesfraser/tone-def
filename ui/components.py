# applied-skills: streamlit
"""Streamlit UI rendering components for ToneDef."""

from __future__ import annotations

import html as html_mod

import streamlit as st

from tonedef.signal_chain_parser import ParsedSignalChain, infer_chain_label

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODIFICATION_COLOURS: dict[str, str] = {
    "unchanged": "#4CAF50",
    "adjusted": "#FF9800",
    "swapped": "#F44336",
    "added": "#9C27B0",
}

CONFIDENCE_DOT: dict[str, str] = {
    "documented": "🟢",
    "inferred": "🟡",
    "estimated": "🔴",
}

EXAMPLE_QUERIES: list[str] = [
    "Jimi Hendrix — Purple Haze rhythm",
    "Pink Floyd — Comfortably Numb solo",
    "Clean jazzy tone with warm reverb",
    "Shoegaze wall-of-sound like My Bloody Valentine",
    "80s new wave jangly clean tone",
    "High gain djent tone, tight and percussive",
]

_INT_ENUM_PREFIXES = ("Cab", "Mic", "MPos")


# ---------------------------------------------------------------------------
# Stepper
# ---------------------------------------------------------------------------


def render_stepper(stage: int) -> None:
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
# Component card
# ---------------------------------------------------------------------------


def render_component_card(comp: dict, schema: dict | None = None) -> None:
    """Render a single component as a styled card with human-readable params."""
    name = html_mod.escape(comp.get("component_name", ""))
    mod = html_mod.escape(comp.get("modification", "—"))
    conf = html_mod.escape(comp.get("confidence", ""))
    rationale = html_mod.escape(comp.get("rationale", ""))
    description = html_mod.escape(comp.get("description", ""))
    params = comp.get("parameters", {})
    base = html_mod.escape(comp.get("base_exemplar", ""))

    mod_colour = MODIFICATION_COLOURS.get(mod, "#666")
    conf_dot = CONFIDENCE_DOT.get(conf, "⚪")

    # Build param_id → param_name lookup from schema
    param_names: dict[str, str] = {}
    if schema and name in schema:
        for p in schema[name].get("parameters", []):
            param_names[p["param_id"]] = p.get("param_name", p["param_id"])

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
            f'<span class="pk">{display_name}</span>: '
            f'<span class="pv">{html_mod.escape(display_val)}</span>'
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


# ---------------------------------------------------------------------------
# Similar presets
# ---------------------------------------------------------------------------


def render_similar_presets(exemplars: list[dict] | None) -> None:
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


# ---------------------------------------------------------------------------
# Tone overview
# ---------------------------------------------------------------------------


def render_tone_overview(parsed: ParsedSignalChain) -> None:
    """Render the tone overview: tag bar + About Your Tone card."""
    ct_label = infer_chain_label(parsed)

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


# ---------------------------------------------------------------------------
# Guitar tips
# ---------------------------------------------------------------------------


def render_guitar_tips(parsed: ParsedSignalChain) -> None:
    """Render the guitar & playing tips card from Phase 1 playing_notes."""
    if parsed.playing_notes:
        st.markdown(
            f'<div class="tone-card"><h4>🎸 Guitar & Playing Tips</h4>'
            f"<p>{html_mod.escape(parsed.playing_notes)}</p></div>",
            unsafe_allow_html=True,
        )

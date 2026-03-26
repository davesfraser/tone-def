# applied-skills: marimo
# Cell plan:
# cell 1:  imports             params ()                                returns (mo, json, re, os)
# cell 2:  project_imports     params ()                                returns (anthropic, load_dotenv, ...)
# cell 3:  setup               params (mo, os, load_dotenv, anthropic)  returns (client, query_input)
# cell 4:  phase1              params (mo, client, query_input, ...)    returns (signal_chain,)
# cell 5:  step1_exemplars     params (mo, signal_chain, ...)           returns (schema, amp_cabinet_lookup, exemplars, exemplar_context)
# cell 6:  step2_manual        params (mo, signal_chain, exemplars, ..) returns (all_manual, all_component_names)
# cell 7:  step7_prompt        params (mo, signal_chain, ...)           returns (prompt,)
# cell 8:  step8_llm           params (mo, json, re, client, ...)      returns (components_raw, raw_response)
# cell 9:  step9_enforce       params (mo, components_raw, ...)         returns (components_final,)
# cell 10: final_summary       params (mo, components_final)            returns ()
# cell 11: build_preset        params (mo, components_final, schema)    returns ()

import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import json
    import os
    import re

    import anthropic
    from dotenv import load_dotenv

    from tonedef.component_mapper import (
        _MATCHED_CABINET_PRO_NAME,
        _find_amp_name,
        _make_matched_cabinet_pro,
        build_cabinet_lookup_context,
        build_component_schema_context,
        build_manual_reference_context,
        fill_defaults,
        load_amp_cabinet_lookup,
        load_schema,
    )
    from tonedef.exemplar_store import format_exemplar_context
    from tonedef.ngrr_builder import transplant_preset
    from tonedef.paths import DATA_EXTERNAL
    from tonedef.prompts import EXEMPLAR_REFINEMENT_PROMPT, SYSTEM_PROMPT
    from tonedef.retriever import (
        get_manual_chunks_for_components,
        search_exemplars,
        search_manual_for_categories,
    )
    from tonedef.xml_builder import build_signal_chain_xml

    return (
        DATA_EXTERNAL,
        EXEMPLAR_REFINEMENT_PROMPT,
        SYSTEM_PROMPT,
        _MATCHED_CABINET_PRO_NAME,
        _find_amp_name,
        _make_matched_cabinet_pro,
        anthropic,
        build_cabinet_lookup_context,
        build_component_schema_context,
        build_manual_reference_context,
        build_signal_chain_xml,
        fill_defaults,
        format_exemplar_context,
        get_manual_chunks_for_components,
        json,
        load_amp_cabinet_lookup,
        load_dotenv,
        load_schema,
        os,
        re,
        search_exemplars,
        search_manual_for_categories,
        transplant_preset,
    )


@app.cell
def _(anthropic, load_dotenv, mo, os):
    load_dotenv()
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    query_input = mo.ui.text_area(
        label="Tone query",
        value="I want the exact guitar tone and processing the black keys used for the chulahoma album",
        full_width=True,
    )
    return client, query_input


@app.cell
def _(SYSTEM_PROMPT, client, mo, query_input):
    mo.stop(not query_input.value, mo.md("*Enter a query above*"))

    _system = SYSTEM_PROMPT.replace("{{TAVILY_RESULTS}}", "No context retrieved.")
    _msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=_system,
        messages=[{"role": "user", "content": query_input.value}],
    )
    signal_chain = _msg.content[0].text

    mo.vstack(
        [
            mo.md("## Phase 1 — Sonic Analysis"),
            mo.md(f"```\n{signal_chain}\n```"),
        ]
    )
    return (signal_chain,)


@app.cell
def _(
    format_exemplar_context,
    load_amp_cabinet_lookup,
    load_schema,
    mo,
    search_exemplars,
    signal_chain,
):
    schema = load_schema()
    amp_cabinet_lookup = load_amp_cabinet_lookup()

    exemplars = search_exemplars(signal_chain)
    exemplar_context = format_exemplar_context(exemplars)

    _rows = []
    for _i, _ex in enumerate(exemplars):
        _comps = [c["component_name"] for c in _ex.get("components", [])]
        _rows.append(f"| {_i + 1} | {_ex.get('preset_name', '?')} | {', '.join(_comps)} |")

    mo.vstack(
        [
            mo.md("## Phase 2 — Step 1: Retrieve exemplars"),
            mo.md("| # | Preset | Components |\n|---|--------|------------|\n" + "\n".join(_rows)),
        ]
    )
    return amp_cabinet_lookup, exemplar_context, exemplars, schema


@app.cell
def _(
    exemplars,
    get_manual_chunks_for_components,
    mo,
    search_manual_for_categories,
    signal_chain,
):
    exemplar_component_names = set()
    for _ex in exemplars:
        for _comp in _ex.get("components", []):
            exemplar_component_names.add(_comp["component_name"])

    manual_for_exemplars = get_manual_chunks_for_components(exemplar_component_names)
    manual_for_additions = search_manual_for_categories(
        signal_chain, exclude_names=exemplar_component_names
    )

    all_manual = manual_for_exemplars + manual_for_additions
    all_component_names = list(
        exemplar_component_names
        | {r["component_name"] for r in manual_for_additions}
        | {_MATCHED_CABINET_PRO_NAME}
    )

    mo.vstack(
        [
            mo.md("## Phase 2 — Steps 2-4: Manual chunk retrieval"),
            mo.md(f"**Exemplar components:** {sorted(exemplar_component_names)}"),
            mo.md(f"**Manual chunks for exemplar components:** {len(manual_for_exemplars)}"),
            mo.md(f"**Manual chunks for additional categories:** {len(manual_for_additions)}"),
            mo.md("Additional: " + ", ".join(r["component_name"] for r in manual_for_additions)),
            mo.md(f"**All schema context names:** {sorted(all_component_names)}"),
        ]
    )
    return all_component_names, all_manual


@app.cell
def _(
    EXEMPLAR_REFINEMENT_PROMPT,
    all_component_names,
    all_manual,
    amp_cabinet_lookup,
    build_cabinet_lookup_context,
    build_component_schema_context,
    build_manual_reference_context,
    exemplar_context,
    mo,
    schema,
    signal_chain,
):
    manual_context = build_manual_reference_context(all_manual)
    schema_context = build_component_schema_context(all_component_names, schema)
    cabinet_context = build_cabinet_lookup_context(amp_cabinet_lookup)

    prompt = (
        EXEMPLAR_REFINEMENT_PROMPT.replace("{{SIGNAL_CHAIN}}", signal_chain)
        .replace("{{EXEMPLAR_PRESETS}}", exemplar_context)
        .replace("{{MANUAL_REFERENCE}}", manual_context)
        .replace("{{COMPONENT_SCHEMA}}", schema_context)
        .replace("{{CABINET_LOOKUP}}", cabinet_context)
    )

    mo.vstack(
        [
            mo.md("## Phase 2 — Step 7: Prompt assembly"),
            mo.md(f"**Prompt length:** {len(prompt):,} chars"),
            mo.md("**Cabinet lookup:**"),
            mo.md(f"```\n{cabinet_context}\n```"),
        ]
    )
    return (prompt,)


@app.cell
def _(amp_cabinet_lookup, client, json, mo, prompt, re):
    _message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_response = _message.content[0].text.strip()

    _raw = raw_response
    if _raw.startswith("```"):
        _raw = re.sub(r"^```[a-z]*\n?", "", _raw)
        _raw = re.sub(r"\n?```$", "", _raw)
    _start = _raw.find("[")
    _end = _raw.rfind("]")
    if _start != -1 and _end != -1 and _end > _start:
        _raw = _raw[_start : _end + 1]

    components_raw = json.loads(_raw)

    _amp_set = {k.lower() for k in amp_cabinet_lookup}
    _rows = []
    for _i, _c in enumerate(components_raw):
        _name = _c.get("component_name", "")
        _is_amp = "**AMP**" if _name.lower() in _amp_set else ""
        _cab = _c.get("parameters", {}).get("Cab", "")
        _cab_str = f"Cab={_cab}" if _cab != "" else ""
        _rows.append(
            f"| {_i + 1} | {_name} | {_c.get('component_id')} "
            f"| {_c.get('modification')} | {_c.get('confidence')} "
            f"| {_c.get('base_exemplar')} | {_is_amp} {_cab_str} |"
        )

    mo.vstack(
        [
            mo.md("## Phase 2 — Step 8: LLM response"),
            mo.md("### Raw response"),
            mo.md(f"```\n{raw_response}\n```"),
            mo.md("### Parsed components"),
            mo.md(
                "| # | Name | ID | Mod | Confidence | Base | Notes |\n"
                "|---|------|----|----|------------|------|-------|\n" + "\n".join(_rows)
            ),
        ]
    )
    return (components_raw,)


@app.cell
def _(amp_cabinet_lookup, components_raw, fill_defaults, mo, schema):
    components_filled = fill_defaults(list(components_raw), schema)

    # Diagnostics before enforcement
    _cabs = [c for c in components_filled if "cabinet" in c.get("component_name", "").lower()]
    _cab_info = [
        f"- {c.get('component_name')} Cab={c.get('parameters', {}).get('Cab')}" for c in _cabs
    ]

    _amp_set = {k.lower() for k in amp_cabinet_lookup}
    _amps = [c for c in components_filled if c.get("component_name", "").lower() in _amp_set]
    _amp_info = [f"- {a.get('component_name')} (id {a.get('component_id')})" for a in _amps]

    # Enforce cabinet
    _base = components_filled[0].get("base_exemplar", "") if components_filled else ""
    components_stripped = [
        c for c in components_filled if "cabinet" not in c.get("component_name", "").lower()
    ]
    detected_amp = _find_amp_name(components_stripped, amp_cabinet_lookup)
    _lookup_val = (
        amp_cabinet_lookup[detected_amp]["cab_value"]
        if detected_amp and detected_amp in amp_cabinet_lookup
        else "N/A (schema default)"
    )
    _cabinet = _make_matched_cabinet_pro(detected_amp, amp_cabinet_lookup, schema, _base)
    _final_cab = _cabinet["parameters"].get("Cab")

    components_final = [*components_stripped, _cabinet]

    mo.vstack(
        [
            mo.md("## Phase 2 — Step 9: Cabinet enforcement"),
            mo.md(f"**Cabinets emitted by LLM:** {len(_cabs)}"),
            mo.md("\n".join(_cab_info) if _cab_info else "*(none)*"),
            mo.md(f"**Amps detected:** {len(_amps)}"),
            mo.md("\n".join(_amp_info) if _amp_info else "*(none)*"),
            mo.md(f"**`_find_amp_name` result:** `{detected_amp!r}`"),
            mo.md(f"**Lookup cab_value:** `{_lookup_val}`"),
            mo.md(f"**Final Matched Cabinet Pro Cab =** `{_final_cab}`"),
        ]
    )
    return (components_final,)


@app.cell
def _(components_final, mo):
    _rows = []
    for _i, _c in enumerate(components_final):
        _params = {
            k: v
            for k, v in _c.get("parameters", {}).items()
            if k in ("Cab", "Pwr", "V", "V1", "V2")
        }
        _rows.append(
            f"| {_i + 1} | {_c.get('component_name')} | {_c.get('component_id')} "
            f"| {_c.get('modification')} | {_params} |"
        )

    mo.vstack(
        [
            mo.md("## Final component list"),
            mo.md(
                "| # | Name | ID | Mod | Key params |\n"
                "|---|------|----|-----|------------|\n" + "\n".join(_rows)
            ),
        ]
    )
    return


@app.cell
def _(
    DATA_EXTERNAL,
    build_signal_chain_xml,
    components_final,
    mo,
    schema,
    transplant_preset,
):
    import tempfile

    _xml = build_signal_chain_xml(components_final, schema)

    with tempfile.NamedTemporaryFile(suffix=".ngrr", delete=False) as _tmp:
        _tmp_path = _tmp.name

    transplant_preset(
        template_path=DATA_EXTERNAL / "Blank_template.ngrr",
        signal_chain_xml=_xml,
        output_path=_tmp_path,
        preset_name="ToneDef Diagnostic Preset",
    )

    # Copy to output directory for easy access
    from tonedef.paths import OUTPUT_PRESETS

    _output_dir = OUTPUT_PRESETS
    _output_dir.mkdir(parents=True, exist_ok=True)
    _out_path = _output_dir / "diagnostic_preset.ngrr"
    with open(_tmp_path, "rb") as _f:
        _out_path.write_bytes(_f.read())

    import os

    os.unlink(_tmp_path)

    mo.vstack(
        [
            mo.md("## Preset generated"),
            mo.md(f"Saved to `{_out_path}`"),
            mo.md("**XML preview (first 500 chars):**"),
            mo.md(f"```xml\n{_xml[:500]}\n```"),
        ]
    )
    return (os,)


if __name__ == "__main__":
    app.run()

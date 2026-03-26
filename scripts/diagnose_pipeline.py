"""Diagnostic script — traces every step of map_components for a given query."""

import json
import os
import re
import sys

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
from tonedef.prompts import EXEMPLAR_REFINEMENT_PROMPT, SYSTEM_PROMPT
from tonedef.retriever import (
    get_manual_chunks_for_components,
    search_exemplars,
    search_manual_for_categories,
)

load_dotenv()
SEP = "=" * 72

query = (
    sys.argv[1]
    if len(sys.argv) > 1
    else ("I want the exact guitar tone and processing the black keys used for the chulahoma album")
)

# --- Phase 1 ----------------------------------------------------------------
print(f"\n{SEP}")
print("PHASE 1 — Sonic Analysis")
print(SEP)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

system = SYSTEM_PROMPT.replace("{{TAVILY_RESULTS}}", "No context retrieved.")
phase1_msg = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2000,
    system=system,
    messages=[{"role": "user", "content": query}],
)
signal_chain = phase1_msg.content[0].text
print(signal_chain)

# --- Phase 2 step-by-step ---------------------------------------------------
print(f"\n{SEP}")
print("PHASE 2 — Step 1: Retrieve exemplars")
print(SEP)

schema = load_schema()
amp_cabinet_lookup = load_amp_cabinet_lookup()

exemplars = search_exemplars(signal_chain)
for i, ex in enumerate(exemplars):
    comp_names = [c["component_name"] for c in ex.get("components", [])]
    print(f"  [{i + 1}] {ex.get('preset_name', '?')} — components: {comp_names}")

exemplar_context = format_exemplar_context(exemplars)

# --- Step 2-4: manual chunks ------------------------------------------------
print(f"\n{SEP}")
print("PHASE 2 — Steps 2-4: Manual chunk retrieval")
print(SEP)

exemplar_component_names: set[str] = set()
for ex in exemplars:
    for comp in ex.get("components", []):
        exemplar_component_names.add(comp["component_name"])
print(f"  Exemplar component names: {sorted(exemplar_component_names)}")

manual_for_exemplars = get_manual_chunks_for_components(exemplar_component_names)
print(f"  Manual chunks for exemplar components: {len(manual_for_exemplars)}")

manual_for_additions = search_manual_for_categories(
    signal_chain, exclude_names=exemplar_component_names
)
print(f"  Manual chunks for additional categories: {len(manual_for_additions)}")
for r in manual_for_additions:
    print(f"    - {r['component_name']}")

all_manual = manual_for_exemplars + manual_for_additions
all_component_names = list(
    exemplar_component_names
    | {r["component_name"] for r in manual_for_additions}
    | {_MATCHED_CABINET_PRO_NAME}
)
print(f"  All component names for schema context: {sorted(all_component_names)}")

# --- Step 7: Build prompt ----------------------------------------------------
print(f"\n{SEP}")
print("PHASE 2 — Step 7: Prompt assembly")
print(SEP)

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
print(f"  Prompt length: {len(prompt)} chars")
print(f"  Cabinet lookup excerpt (first 500 chars):\n{cabinet_context[:500]}")

# --- Step 8: LLM call -------------------------------------------------------
print(f"\n{SEP}")
print("PHASE 2 — Step 8: LLM call")
print(SEP)

message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    messages=[{"role": "user", "content": prompt}],
)

raw = message.content[0].text.strip()
print("  RAW LLM RESPONSE:")
print(raw)

# Parse
if raw.startswith("```"):
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

start = raw.find("[")
end = raw.rfind("]")
if start != -1 and end != -1 and end > start:
    raw = raw[start : end + 1]

components: list[dict] = json.loads(raw)

print(f"\n  PARSED COMPONENTS ({len(components)}):")
for i, comp in enumerate(components):
    print(
        f"    [{i + 1}] {comp.get('component_name')} (id {comp.get('component_id')})"
        f" — mod={comp.get('modification')} conf={comp.get('confidence')}"
        f" base={comp.get('base_exemplar')}"
    )
    if comp.get("component_name", "").lower() in {k.lower() for k in amp_cabinet_lookup}:
        print("         ^^^ THIS IS AN AMP (in lookup table)")
    cab_val = comp.get("parameters", {}).get("Cab")
    if cab_val is not None:
        print(f"         Cab parameter = {cab_val}")

# --- Step 9: Fill defaults + enforce cabinet ---------------------------------
print(f"\n{SEP}")
print("PHASE 2 — Step 9: Fill defaults + cabinet enforcement")
print(SEP)

components = fill_defaults(components, schema)

# Check for cabinet components before stripping
cabinets_before = [c for c in components if "cabinet" in c.get("component_name", "").lower()]
print(f"  Cabinet components before strip: {len(cabinets_before)}")
for cab in cabinets_before:
    print(f"    - {cab.get('component_name')} Cab={cab.get('parameters', {}).get('Cab')}")

# Check all amps before stripping
amps_before = [
    c
    for c in components
    if c.get("component_name", "").lower() in {k.lower() for k in amp_cabinet_lookup}
]
print(f"  Amp components before strip: {len(amps_before)}")
for amp in amps_before:
    print(f"    - {amp.get('component_name')} (id {amp.get('component_id')})")

base_exemplar = components[0].get("base_exemplar", "") if components else ""
components = [c for c in components if "cabinet" not in c.get("component_name", "").lower()]

amp_name = _find_amp_name(components, amp_cabinet_lookup)
print(f"  _find_amp_name result: {amp_name!r}")
if amp_name and amp_name in amp_cabinet_lookup:
    print(f"  Lookup cab_value for {amp_name!r}: {amp_cabinet_lookup[amp_name]['cab_value']}")
else:
    print("  No match in lookup — will use schema default Cab")

cabinet = _make_matched_cabinet_pro(amp_name, amp_cabinet_lookup, schema, base_exemplar)
print(f"  Final Matched Cabinet Pro Cab = {cabinet['parameters'].get('Cab')}")

components.append(cabinet)

# --- Final output ------------------------------------------------------------
print(f"\n{SEP}")
print("FINAL COMPONENT LIST")
print(SEP)
for i, comp in enumerate(components):
    params_summary = {
        k: v for k, v in comp.get("parameters", {}).items() if k in ("Cab", "Pwr", "V", "V1", "V2")
    }
    print(
        f"  [{i + 1}] {comp.get('component_name')} (id {comp.get('component_id')})"
        f" — {comp.get('modification')} — key params: {params_summary}"
    )

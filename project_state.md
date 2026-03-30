# ToneDef — Project State

## What ToneDef Is

A chat-based guitar tone matching application. Users describe a tone in natural
language; ToneDef identifies the signal chain, explains the reasoning with
provenance labels, maps hardware to Guitar Rig 7 components, and generates a
loadable .ngrr preset file.

## Product Vision

A guitarist opens ToneDef, types something like "I want the tone from Where The
Streets Have No Name" or "give me a warm bluesy crunch like SRV" or "I want
something super fizzy and trebly and aggressive", and within seconds receives:

1. A natural language explanation of the signal chain — what hardware, why,
   with honest provenance labels (DOCUMENTED / INFERRED / ESTIMATED)
2. A downloadable .ngrr preset file they can drag straight into Guitar Rig 7

The key value proposition: the gap between "I want that sound" and "I have that
sound loaded in my software" goes from hours of research and tweaking to seconds.

ToneDef is also a portfolio project demonstrating real-world GenAI engineering —
RAG, structured output, binary file generation, prompt engineering with provenance
and fallback behaviour, a full data pipeline from raw presets to production mapping.

## End-to-End Flow (implemented)

```
User query (Streamlit UI)
        │
        ▼
SYSTEM_PROMPT (phase 1)
  - Sonic analysis (internal, not shown)
  - Signal chain recommendation with hardware names
  - Cabinet and mic recommendation
  - Knowledge provenance labels
  - GR browser tag inference
        │
        ▼
Signal chain output (shown to user as human-readable explanation)
        │
        ▼
map_components() in component_mapper.py (phase 2)
  - Retrieves top-5 tonally similar factory presets (exemplars) via ChromaDB
  - Gathers manual descriptions for exemplar components + missing categories
  - Loads amp-to-cabinet lookup for deterministic cabinet assignment
  - Calls EXEMPLAR_REFINEMENT_PROMPT — LLM adjusts best exemplar to match target
  - Enforces correct cabinet via amp_cabinet_lookup.json
  - Outputs structured JSON: [{component_name, component_id, base_exemplar, modification, parameters}]
        │
        ▼
build_signal_chain_xml() in xml_builder.py
  - Assembles <non-fix-components> XML from JSON
  - Clamps and validates parameter values against component schema
  - Injects GR browser tags from phase 1
        │
        ▼
transplant_preset() in ngrr_builder.py
  - Injects XML into blank template
  - Updates all binary fields (LMX, remaining-bytes, UUIDs)
  - Writes valid .ngrr file
        │
        ▼
Download link shown to user in Streamlit UI
```

## Architecture

### Two-phase LLM pipeline

**Phase 1 — SYSTEM_PROMPT**
Input: user tone query
Output: natural language signal chain with hardware names, provenance labels
(DOCUMENTED/INFERRED/ESTIMATED), cabinet and mic recommendation, GR browser tags

**Phase 2 — EXEMPLAR_REFINEMENT_PROMPT**
Input: phase 1 output + top-5 exemplar presets + manual descriptions + component schema + cabinet lookup
Output: structured JSON list of GR7 components with normalised 0.0-1.0 parameter values

### Exemplar-first architecture
- 1425 factory presets indexed in exemplar_store.json and ChromaDB
- search_exemplars() returns top-5 tonally similar presets
- get_manual_chunks_for_components() retrieves manual docs for exemplar components
- search_manual_for_categories() fills gaps for missing effect categories
- LLM selects the best exemplar as a starting point and adjusts it to match the tonal target
- Cabinet assignment is deterministic via amp_cabinet_lookup.json (27 amps → Matched Cabinet Pro with correct Cab enum value)

---

## Current Status

### Source modules (`src/tonedef/`)

| Module | Purpose |
|--------|---------|
| `ngrr_builder.py` | Reverse-engineered NI Monolith binary format. Generates valid loadable .ngrr preset files. Critical step ordering: inject signal chain → update preset name → update rb fields → update byte 0 file size → update both LMX fields → fresh UUIDs. |
| `ngrr_parser.py` | Parses .ngrr files: extract_xml1, extract_xml2, extract_preset_name, parse_non_fix_components, merge_into_catalogue, finalise_catalogue, merge_tags_into_catalogue, finalise_tag_catalogue, parse_preset_metadata. |
| `xml_builder.py` | Assembles valid `<non-fix-components>` XML from component JSON. Clamps parameter values to schema-defined min/max ranges, falls back to param midpoint when no value provided. |
| `component_mapper.py` | Phase 2 orchestrator: search exemplars → gather manual context → build prompt → LLM call → validate → enforce cabinet. Also loads schema and amp_cabinet_lookup. |
| `exemplar_store.py` | Factory preset exemplar dataset for few-shot grounding: build_exemplar_records, _invert_tag_catalogue, format_exemplar_context. |
| `retriever.py` | ChromaDB retrieval layer: search_exemplars (tonal query → similar presets), get_manual_chunks_for_components (exact-match docs), search_manual_for_categories (category-stratified search). |
| `prompts.py` | Two system prompts: SYSTEM_PROMPT (Phase 1 — tone query → signal chain) and EXEMPLAR_REFINEMENT_PROMPT (Phase 2 — exemplar-first preset builder). |
| `models.py` | Pydantic models: ParsedSignalChain, ComponentOutput, PresetMetadata. |
| `pipeline.py` | End-to-end orchestration: query → Phase 1 → Phase 2 → XML → .ngrr. |
| `signal_chain_parser.py` | Parses the Phase 1 LLM text output into structured ParsedSignalChain (chain type, tags, components, playing notes, etc.). |
| `validation.py` | Pure validation functions for Phase 1/2 output — tag checks, component counts, cabinet enforcement, order validation. User-facing plain-English messages. |
| `crp_lookup.py` | Control Room Pro cabinet/mic/position enum lookup from crp_enum_lookup.json. 0-indexed enums: 31 cabinets (0–30), 5 mics (0–4), 3 positions (0–2). |
| `tonal_vocab.py` | Tonal descriptor vocabulary for modifier UI chips. Loads tonal_descriptors.json and provides term selection helpers. |
| `paths.py` | Centralised filesystem paths — all modules import paths from here. |
| `settings.py` | Pydantic Settings configuration — API key (SecretStr), model name, temperature, etc. |

### Data pipeline scripts (`scripts/`)

| Script | Purpose |
|--------|---------|
| `build_component_schema.py` | Parses all .ngrr → component_schema.json |
| `build_tag_catalogue.py` | Parses all .ngrr → tag_catalogue.json |
| `build_manual_chunks.py` | Extracts component chunks from GR7 manual PDF → gr_manual_chunks.json |
| `build_retrieval_index.py` | Indexes gr_manual_chunks.json into ChromaDB |
| `build_exemplar_index.py` | Indexes 1425 factory presets → exemplar_store.json |
| `build_amp_cabinet_lookup.py` | Scans exemplar store for amp→cabinet Cab values → amp_cabinet_lookup.json |
| `build_crp_lookup.py` | Builds Control Room Pro enum lookup → crp_enum_lookup.json |
| `check_pipeline.py` | Quick end-to-end pipeline sanity check |
| `diagnose_pipeline.py` | Detailed pipeline diagnostic with intermediate outputs |
| `_analyze_modes.py` | (diagnostic) Analyse component mode distributions |
| `_audit_ranges.py` | (diagnostic) Audit parameter value ranges across presets |
| `_check_factory_formats.py` | (diagnostic) Verify factory preset format consistency |
| `_verify_cab.py` | (diagnostic) Verify cabinet enum assignments |

### Data files (`data/processed/`)

| File | Contents |
|------|----------|
| `component_schema.json` | 147 unique GR7 components with parameter stats |
| `tag_catalogue.json` | 111 unique tags (Characters 16, FX Types 70, Genres 14, Input Sources 11) |
| `gr_manual_chunks.json` | 118 component chunks from GR7 manual |
| `exemplar_store.json` | 1425 preset exemplar records |
| `amp_cabinet_lookup.json` | 27 amp → Matched Cabinet Pro Cab value mappings |
| `crp_enum_lookup.json` | CRP enums: 31 cabinets (0–30), 5 mics (0–4), 3 positions (0–2) |
| `tonal_descriptors.json` | Tonal modifier vocabulary for UI chips |
| `chromadb/` | ChromaDB persistent collections (gr_manual, gr_exemplars) |
| `output_presets/` | Generated .ngrr presets for testing |

### Tests (`tests/`) — 317 tests, all passing

| File | Coverage |
|------|----------|
| `test_smoke.py` | Basic import and API checks |
| `test_ngrr_parser.py` | Parsing, catalogue merge, metadata, tag filtering |
| `test_ngrr_builder.py` | Name update, rb fields, UUIDs, transplant integration |
| `test_exemplar_store.py` | Catalogue inversion, context formatting, build records |
| `test_xml_builder.py` | XML structure, parameter clamping, UUIDs, multi-component |
| `test_component_mapper.py` | Context builders, cabinet lookup, fill defaults, Cabinet Pro, CRP enums |
| `test_signal_chain_parser.py` | Chain type detection, tag extraction, component parsing |
| `test_validation.py` | All validation rules, user-facing messages, edge cases |
| `test_models.py` | Pydantic model construction and validation |
| `test_retriever.py` | Exemplar search, manual chunk lookup, category search |
| `test_crp_lookup.py` | CRP enum resolution, fallback behaviour |
| `test_tonal_vocab.py` | Descriptor loading, term selection, category filtering |
| `test_pipeline.py` | End-to-end pipeline orchestration |
| `test_prompts.py` | Prompt template integrity, placeholder presence |

### Streamlit app (`app.py`)

Single-page progressive flow: tone description → tonal modifiers → Phase 1 (signal chain) →
Phase 2 (component mapping) → XML → .ngrr binary → download. Features: stepper bar, styled
component cards with rationale and human-readable params, tone overview with tag pills,
guitar tips, similar presets section, custom dark theme CSS. HTML-escaped user and LLM content.

### Notebooks (`notebooks/marimo/`)

| File | Purpose |
|------|---------|
| `01_ngrr_preset_builder.py` | Binary preset transplant pipeline |
| `02_component_schema_parser.py` | Component parsing and schema exploration |
| `03_tag_catalogue_builder.py` | Tag parsing and catalogue structure |
| `04_phase1_evaluation.py` | Phase 1 signal chain validation |
| `05_retrieval_evaluation.py` | Exemplar retrieval quality assessment |
| `06_phase2_evaluation.py` | Component mapping validation |
| `07_end_to_end.py` | Full pipeline execution and output review |

### Pending

1. **Tavily RAG** — `{{TAVILY_RESULTS}}` placeholder in SYSTEM_PROMPT. Deferred —
   system produces good results without it. Low priority.
2. **V4 iterative refinement** — chat-based follow-up ("make it brighter", "add more
   reverb"). Requires session state management and diff-based editing.

---

## Key Decisions

- FULL_PRODUCTION chain type = "gear archaeology" — reference/education not replication
- Preset generation uses blank template transplant approach
- Amplifiers tag category excluded from tag catalogue — redundant with component selection
- Cabinet and mic recommendation mandatory for ALL chain types
- Phase 2 uses exemplar-first architecture — LLM adjusts factory presets rather than building from scratch
- Cabinet assignment is deterministic via amp_cabinet_lookup.json (Cab is integer enum, not normalised float)
- CRP cabinet enums are 0-indexed (0–30): 0=DI Box, 1=Nothing (bypass), 2–28=named cabs, 29=Rammfire A, 30=Rammfire B
- Google Sheet equivalencies source dropped — LLM-generated, unreliable
- Ali Jamieson page used only for unambiguous 1:1 mappings (no hedging language)
- GR7 manual is primary source for component identification via manual chunks

## File Structure

```
src/tonedef/
    paths.py              — project path constants
    settings.py           — configuration values
    ngrr_builder.py       — preset generation (transplant_preset etc.)
    ngrr_parser.py        — preset parsing (extract_xml1/2, parse_non_fix_components etc.)
    xml_builder.py        — XML assembly from component JSON
    component_mapper.py   — phase 2 orchestrator (exemplar retrieval, LLM call, cabinet enforcement)
    exemplar_store.py     — preset exemplar dataset (build, query, format)
    retriever.py          — ChromaDB retrieval (exemplar, manual chunk, category search)
    prompts.py            — SYSTEM_PROMPT, EXEMPLAR_REFINEMENT_PROMPT

scripts/
    build_component_schema.py
    build_tag_catalogue.py
    build_manual_chunks.py
    build_retrieval_index.py
    build_exemplar_index.py
    build_amp_cabinet_lookup.py
    check_pipeline.py

tests/
    test_smoke.py
    test_ngrr_parser.py
    test_ngrr_builder.py
    test_xml_builder.py
    test_exemplar_store.py
    test_component_mapper.py

data/
    external/
        Blank template.ngrr           — blank GR7 preset template
        gr_equivalencies_alijamieson.txt
        presets/                      — 1425 factory .ngrr presets
    processed/
        component_schema.json         — 147 components with parameter stats
        amp_cabinet_lookup.json       — amp name → Matched Cabinet Pro id mapping
        tag_catalogue.json            — 111 tags
        gr_manual_chunks.json         — 118 component chunks from manual
        exemplar_store.json           — 1425 preset exemplar records
        chromadb/                     — ChromaDB persistent collection

notebooks/marimo/
    01_test_api.py
    02_ngrr_preset_builder.py
    03_component_schema_parser.py
    05_tag_catalogue_builder.py
    08_exemplar_store.py
```

## Stack

uv / ruff / marimo / pytest / Streamlit / anthropic SDK / chromadb
Python 3.13, Windows development machine

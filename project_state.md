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
  - Extracts hardware names from phase 1 output
  - Named hardware route: component_mapping.json lookup
  - Descriptor route: ChromaDB semantic search via retriever.py
  - Exemplar grounding: search_exemplars() → format_exemplar_context()
  - Calls COMPONENT_SELECTION_PROMPT or DESCRIPTOR_SELECTION_PROMPT
  - Outputs structured JSON: [{component_name, component_id, parameters: {id: value}}]
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

**Phase 2 — COMPONENT_SELECTION_PROMPT / DESCRIPTOR_SELECTION_PROMPT**
Input: phase 1 output + component mapping + ChromaDB retrieval + preset exemplars
Output: structured JSON list of GR7 components with normalised 0.0-1.0 parameter values

### Two routing paths in phase 2
- Named hardware route: hardware name → component_mapping.json lookup → component id
- Descriptor route: sonic profile → ChromaDB semantic search → DESCRIPTOR_SELECTION_PROMPT

### Exemplar grounding
- 1425 factory presets indexed in exemplar_store.json
- search_exemplars() returns top-N most tonally similar presets by query
- format_exemplar_context() formats them as few-shot signal chain examples
- Injected as {{EXEMPLAR_PRESETS}} in COMPONENT_SELECTION_PROMPT

---

## Current Status

### Completed

**ngrr_builder.py** (`src/tonedef/`)
Reverse-engineered NI Monolith binary format. Proven working — generates valid
loadable .ngrr preset files. Critical step ordering:
1. Inject signal chain
2. Update preset name (changes XML1 size)
3. Update rb fields (after name change so positions are final)
4. Update byte 0 file size
5. Update both LMX fields (after name change so XML1 size is final)
6. Fresh UUIDs

Key discovery: two LMX markers exist (one before XML1, one before XML2). Missing
the XML1 LMX update was the root cause of files failing to import into GR7.

**ngrr_parser.py** (`src/tonedef/`)
Parses .ngrr files: extract_xml1, extract_xml2, extract_preset_name,
parse_non_fix_components, merge_into_catalogue, finalise_catalogue,
merge_tags_into_catalogue, finalise_tag_catalogue, parse_preset_metadata

**xml_builder.py** (`src/tonedef/`)
Assembles valid `<non-fix-components>` XML from component JSON output.
Clamps parameter values to schema-defined min/max ranges, falls back to
param midpoint when no value provided, generates fresh UUIDs per component.

**component_mapper.py** (`src/tonedef/`)
Runtime phase 2 orchestrator:
- `build_hardware_index` / `lookup_hardware` — component_mapping.json lookups
- `extract_hardware_names` — regex extraction of hardware from phase 1 output
- `fill_defaults` — applies schema defaults for missing parameter values
- `map_components` — full pipeline: extract → lookup → retrieve → LLM → validate

**exemplar_store.py** (`src/tonedef/`)
Preset exemplar dataset for few-shot grounding:
- `build_exemplar_records` — parses all factory presets → structured records
- `_invert_tag_catalogue` — tag path → display name lookup
- `format_exemplar_context` — formats top-N exemplars as {{EXEMPLAR_PRESETS}} block

**retriever.py** (`src/tonedef/`)
ChromaDB retrieval layer:
- `search_by_hardware` — hardware name → component manual chunk lookup
- `search_by_descriptor` — sonic descriptor → relevant component chunks
- `search_exemplars` — tonal query → similar preset exemplars (stratified by tag root)
- `collection_path` — path to ChromaDB persistent collection

**prompts.py** (`src/tonedef/`)
- SYSTEM_PROMPT — complete with sonic_analysis, chain_type_detection,
  cabinet_and_mic, knowledge_transparency, fallback_behaviour, tag_inference
- MAPPING_PROMPT — for component mapping generation
- COMPONENT_SELECTION_PROMPT — phase 2 named-hardware route with exemplar grounding
- DESCRIPTOR_SELECTION_PROMPT — phase 2 descriptor/fallback route

**Data pipeline scripts** (`scripts/`)
- build_component_schema.py — parses all .ngrr → data/processed/component_schema.json
- build_tag_catalogue.py — parses all .ngrr → data/processed/tag_catalogue.json
- build_manual_chunks.py — extracts component chunks from GR7 manual PDF →
  data/processed/gr_manual_chunks.json
- generate_component_mapping.py — three-tier LLM mapping generation
- promote_component_mapping.py — validates reviewed CSV →
  data/processed/component_mapping.json
- build_retrieval_index.py — indexes gr_manual_chunks.json into ChromaDB
- build_exemplar_index.py — indexes 1425 factory presets → exemplar_store.json

**Data files produced**
- data/processed/component_schema.json — 147 unique GR7 components with parameter stats
- data/processed/component_mapping.json — hardware alias → component id mapping
- data/processed/tag_catalogue.json — 111 unique tags (Characters 16, FX Types 70,
  Genres 14, Input Sources 11)
- data/processed/gr_manual_chunks.json — 118 component chunks from GR7 manual
- data/processed/exemplar_store.json — 1425 preset exemplar records
- data/processed/chromadb/ — ChromaDB persistent collection

**Tests** (`tests/`) — 106 tests, all passing
- test_smoke.py — basic import and API checks
- test_ngrr_parser.py — 22 tests (parsing, catalogue merge, metadata, tag filtering)
- test_ngrr_builder.py — 10 tests (name update, rb fields, UUIDs, transplant integration)
- test_exemplar_store.py — 13 tests (catalogue inversion, context formatting, build records)
- test_xml_builder.py — 18 tests (XML structure, parameter clamping, UUIDs, multi-component)
- test_component_mapper.py — 36 tests (index lookups, context builders, defaults, extraction)

**Streamlit app** (`app.py`)
Fully wired end-to-end: phase 1 → map_components() → xml_builder → transplant_preset →
download link. Uses exemplar grounding and ChromaDB retrieval in phase 2.

**Notebooks** (`notebooks/marimo/`)
- 02_ngrr_preset_builder.py — demonstrates preset transplant pipeline
- 03_component_schema_parser.py — demonstrates component parsing
- 04_component_mapping_generation.py — demonstrates three-tier mapping generation
- 05_tag_catalogue_builder.py — demonstrates tag parsing
- 06_phase2_component_pipeline.py — demonstrates full phase 2 pipeline
- 07_chromadb_retrieval.py — demonstrates ChromaDB retrieval
- 08_exemplar_store.py — demonstrates exemplar store and context formatting

### Pending

1. **Tavily RAG** — `{{TAVILY_RESULTS}}` placeholder in SYSTEM_PROMPT. Deferred —
   system produces good results without it. Low priority.
2. **V4 iterative refinement** — chat-based follow-up ("make it brighter", "add more
   reverb"). Requires session state management and diff-based editing.

---

## Key Decisions

- FULL_PRODUCTION chain type = "gear archaeology" — reference/education not replication
- Preset generation uses blank template transplant approach
- Component mapping uses long-format CSV (one row per hardware alias per component)
- Amplifiers tag category excluded from tag catalogue — redundant with component mapping
- Cabinet and mic recommendation mandatory for ALL chain types
- Few-shot exemplars live in COMPONENT_SELECTION_PROMPT
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
    component_mapper.py   — phase 2 orchestrator (hardware lookup, LLM call, defaults)
    exemplar_store.py     — preset exemplar dataset (build, query, format)
    retriever.py          — ChromaDB retrieval (hardware, descriptor, exemplar search)
    prompts.py            — SYSTEM_PROMPT, MAPPING_PROMPT, COMPONENT_SELECTION_PROMPT,
                            DESCRIPTOR_SELECTION_PROMPT

scripts/
    build_component_schema.py
    build_tag_catalogue.py
    build_manual_chunks.py
    generate_component_mapping.py
    promote_component_mapping.py
    build_retrieval_index.py
    build_exemplar_index.py

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
        component_mapping.json        — hardware alias → component id mapping
        tag_catalogue.json            — 111 tags
        gr_manual_chunks.json         — 118 component chunks from manual
        exemplar_store.json           — 1425 preset exemplar records
        chromadb/                     — ChromaDB persistent collection

notebooks/marimo/
    02_ngrr_preset_builder.py
    03_component_schema_parser.py
    04_component_mapping_generation.py
    05_tag_catalogue_builder.py
    06_phase2_component_pipeline.py
    07_chromadb_retrieval.py
    08_exemplar_store.py
```

## Stack

uv / ruff / marimo / pytest / Streamlit / anthropic SDK / chromadb
Python 3.13, Windows development machine

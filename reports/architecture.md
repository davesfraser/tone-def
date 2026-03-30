# ToneDef — Architecture & Approach

## 1. Problem Statement

Guitarists often know exactly what tone they want but face a significant gap
between "I want that sound" and actually dialling it in. Guitar Rig 7 offers
hundreds of components with thousands of parameters — navigating that space
manually takes hours of research and experimentation.

ToneDef bridges this gap. A user types a natural language description — a
reference recording, a genre, a set of adjectives — and receives a downloadable
`.ngrr` preset file they can drag straight into Guitar Rig 7.

## 2. Two-Phase LLM Architecture

The pipeline splits the problem into two distinct LLM calls, each with a
focused responsibility.

### Phase 1 — Signal Chain Generation (`SYSTEM_PROMPT`)

**Input:** user tone query + optional tonal modifiers
**Output:** structured natural-language signal chain with:

- Chain type classification (`AMP_ONLY` or `FULL_PRODUCTION`)
- Hardware unit names with provenance labels (`DOCUMENTED` / `INFERRED` / `ESTIMATED`)
- Guitar Rig 7 equivalents for each hardware unit
- Cabinet and microphone recommendation
- GR7 browser tags (genre + character)
- Confidence rating and narrative explanation

The Phase 1 output is shown to the user as the "About Your Tone" section. It is
also parsed into a `ParsedSignalChain` dataclass by `signal_chain_parser.py` using
regex patterns to extract chain type, sections, units, parameters, tags, and
narrative text.

### Phase 2 — Component Mapping (`EXEMPLAR_REFINEMENT_PROMPT`)

**Input:** Phase 1 signal chain + exemplar presets + manual docs + component schema + cabinet lookup
**Output:** JSON array of GR7 components with normalised 0.0–1.0 parameter values

Phase 2 uses an exemplar-first strategy: the LLM selects the closest factory
preset as a starting point and adjusts it to match the tonal target. This
produces more realistic parameter combinations than generating values from
scratch.

## 3. Exemplar-First RAG Strategy

Factory presets are the strongest grounding signal. Each of the 1,425 factory
presets is parsed into a structured record containing component names, parameter
values, and browser tags. These are indexed in an exemplar store and scored
against user queries.

**Why exemplar-first works:**

- Factory presets contain *proven-good* parameter combinations that NI sound
  designers validated
- Starting from a real preset and adjusting is more reliable than generating
  parameter values from a blank slate
- Tags (genre + character) provide semantic overlap with natural language queries
- Component overlap between query intent and preset composition provides
  structural matching

**Exemplar scoring** combines tag similarity (Jaccard on controlled vocabulary)
and component overlap, with configurable weights. The top-5 exemplars are
formatted as reference context for the Phase 2 prompt.

## 4. Offline Data Pipeline

Seven scripts in `scripts/` build the processed data files from raw sources.
Each is deterministic and idempotent.

```
Factory .ngrr presets (data/external/presets/)
        │
        ├──► build_component_schema.py ──► component_schema.json (147 components)
        ├──► build_tag_catalogue.py ──► tag_catalogue.json (111 tags)
        ├──► build_exemplar_index.py ──► exemplar_store.json (1,425 presets)
        └──► build_amp_cabinet_lookup.py ──► amp_cabinet_lookup.json (27 amps)

GR7 Manual PDF (data/external/)
        └──► build_manual_chunks.py ──► gr_manual_chunks.json (118 chunks)
                └──► build_retrieval_index.py ──► chromadb/ (persistent collections)

Factory .ngrr presets (CRP components)
        └──► build_crp_lookup.py ──► crp_enum_lookup.json (31 cabs, 5 mics, 3 positions)
```

### Key data files

| File | Records | Purpose |
|------|---------|---------|
| `component_schema.json` | 147 components | Parameter names, IDs, min/max/default stats |
| `tag_catalogue.json` | 111 tags | GR7 browser tag hierarchy |
| `exemplar_store.json` | 1,425 presets | Parsed factory presets with components + tags |
| `amp_cabinet_lookup.json` | 27 mappings | Amp → deterministic Cab enum for Matched Cabinet Pro |
| `gr_manual_chunks.json` | 118 chunks | Component descriptions from the GR7 manual |
| `crp_enum_lookup.json` | 39 enums | CRP cabinet (0–30), mic (0–4), position (0–2) enums |
| `tonal_descriptors.json` | — | Modifier vocabulary for UI tonal chips |

## 5. Runtime Pipeline

```
User query (Streamlit UI)
    │
    ▼
compose_query(text, modifiers) ─── pipeline.py
    │
    ▼
generate_signal_chain(query) ─── Phase 1 LLM call
    │
    ▼
parse_signal_chain(raw_text) ─── signal_chain_parser.py
    │   Extracts: chain_type, sections, units, tags, confidence,
    │             chain_type_reason, why_it_works, playing_notes
    │
    ├──► validate_phase1(parsed) ─── validation.py
    │
    ▼
map_components(signal_chain, parsed) ─── component_mapper.py
    │
    │   1. search_exemplars() → top-5 factory presets
    │   2. format_exemplar_context() → exemplar reference text
    │   3. get_manual_chunks_for_components() → exact-match manual docs
    │   4. search_manual_for_categories() → gap-fill by effect category
    │   5. search_manual_by_tonal_target() → tonal similarity candidates
    │   6. Assemble prompt with 7 substitution blocks
    │   7. Phase 2 LLM call → JSON component array
    │   8. Pydantic validation + fill_defaults + cabinet enforcement
    │
    ├──► validate_phase2(components, schema)
    ├──► validate_signal_chain_order(components, amp_cabinet_lookup)
    ├──► validate_pre_build(components)
    │
    ▼
build_signal_chain_xml(components, schema, tags) ─── xml_builder.py
    │   Assembles <non-fix-components> XML, clamps params to schema ranges,
    │   generates fresh UUIDs per component
    │
    ▼
transplant_preset(template, xml, output, name) ─── ngrr_builder.py
    │   1. Inject signal chain into blank template
    │   2. Update preset name
    │   3. Update remaining-bytes fields
    │   4. Update byte 0 file size
    │   5. Update both LMX markers
    │   6. Fresh UUIDs
    │
    ▼
.ngrr binary file → download button in Streamlit UI
```

## 6. Binary Format (.ngrr)

Guitar Rig 7 presets use NI's Monolith container format. Key structural elements:

| Offset | Field | Format |
|--------|-------|--------|
| Bytes 0–3 | Total file size | uint32 little-endian |
| Bytes 24–40 | Main UUID | 16-byte binary |
| Before XML1 | LMX marker | `0x204c4d58` with size fields at ±8 bytes |
| XML1 | `guitarrig7-database-info` | UTF-8 XML (preset metadata, name, tags) |
| Before XML2 | LMX marker | Same structure as XML1 marker |
| XML2 | `gr-instrument-chunk` | UTF-8 XML (signal chain — `<non-fix-components>`) |
| `hsin` chunks | UUID positions | 16-byte UUID at `hsin` marker + 8 |

**Transplant strategy:** Rather than building a binary file from scratch, ToneDef
injects the generated signal chain XML into a known-good blank template. This
avoids reverse-engineering every byte of the container format — only the fields
that change (signal chain, preset name, sizes, UUIDs) need updating.

**Critical discovery:** Two LMX markers exist — one before XML1 and one before
XML2. Both contain size+13 and size+1 fields. Missing the XML1 LMX update was the
root cause of early failures where presets wouldn't import into GR7.

## 7. Validation Layers

Four validation stages catch problems before they reach the binary builder:

| Stage | Function | Checks |
|-------|----------|--------|
| Phase 1 | `validate_phase1()` | Chain type valid, sections non-empty, units have names |
| Retrieval | `validate_retrieval()` | Exemplars found, minimum similarity score |
| Phase 2 | `validate_phase2()` | Component names/IDs/params exist in schema, values in range |
| Pre-build | `validate_signal_chain_order()` + `validate_pre_build()` | Amp present, cabinet after amp, no empty presets, no duplicate IDs |

All validation functions return a `ValidationResult(errors, warnings)` dataclass.
Errors block preset generation; warnings are shown to the user but don't prevent
the build.

All user-facing validation messages are written in plain English — no internal
field names, enum values, or code references leak to the user.

## 8. Cabinet Assignment: CRP and MCP Strategies

Cabinet assignment is the most constrained part of the pipeline because GR7's
cabinet parameters use integer enums (not normalised floats).

### Matched Cabinet Pro (MCP) — default strategy

When the LLM doesn't emit a Control Room component, the pipeline creates a
`Matched Cabinet Pro` (component ID 156000) with deterministic cab assignment:

1. **Cab value** always from `amp_cabinet_lookup.json` (amp-specific, extracted
   from factory presets)
2. **LLM params** layered on top (if the LLM set Mic, Bass, etc.)
3. **Exemplar params** from the best-matching factory preset
4. **Schema defaults** as final fallback

This 4-tier layering ensures every amp gets its known-good cab while still
allowing the LLM to adjust tonal parameters.

### Control Room Pro (CRP) — full production strategy

For `FULL_PRODUCTION` chains, the LLM may emit Control Room or Control Room Pro
components with explicit cabinet/mic/position selections. These use 0-indexed
integer enums:

- **Cabinets (Cab1–Cab8):** 0–30 (0 = DI Box, 1 = Nothing/bypass, 2–28 = named cabinets, 29 = Rammfire A, 30 = Rammfire B)
- **Microphones (Mic1–Mic8):** 0–4 (5 mic models)
- **Mic positions (MPos1–MPos8):** 0–2 (3 position options)

The pipeline validates all CRP integer params are within range and casts them
to `int` (LLM sometimes returns floats).

## 9. Streamlit UI Flow

The app uses a single-page progressive layout with three stages:

**Stage 0 — Input:** Text area for tone description, tonal modifier chips
(genre, character, style adjectives), example query buttons.

**Stage 1 — Processing:** Spinner while Phase 1 and Phase 2 execute.

**Stage 2 — Results:**
- Stepper bar showing progress (Describe → Generate → Results)
- Query summary bar with modifier badges
- Tag pills (chain type, genres, characters)
- "About Your Tone" narrative card (chain_type_reason + why_it_works)
- "Guitar & Playing Tips" card (playing_notes from Phase 1)
- Validation warnings/errors
- Similar presets analysed (collapsible)
- Signal chain component cards with:
  - Component name, modification type, confidence dot
  - Human-readable parameters (0–10 scale, On/Off for switches)
  - Rationale for component selection
  - Base exemplar origin
- Download section with editable preset name

All user input and LLM-generated content is HTML-escaped before rendering
via `unsafe_allow_html=True` to prevent XSS.

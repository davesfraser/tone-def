# Data

This directory holds all data for **ToneDef**.

Raw inputs are treated as read-only. Processed outputs are derived and
reproducible from raw (with two exceptions noted below).

---

## Directory structure

| Directory     | Purpose                                                |
|--------------|--------------------------------------------------------|
| `raw/`       | Original source data — never modified after download   |
| `interim/`   | Partially processed or filtered working files          |
| `processed/` | Clean, analysis-ready outputs from the pipeline        |
| `external/`  | Third-party reference data or downloaded resources     |

Most data files are gitignored. The folder structure is version-controlled
via `.gitkeep` files. See exceptions below.

---

## Data sources

### Factory presets (gitignored)

| Field         | Detail                                                   |
|--------------|----------------------------------------------------------|
| Source       | Guitar Rig 7 factory preset library                       |
| Access       | Installed with Guitar Rig 7. Path configured via `GR7_PRESETS_DIR` in `.env` |
| Location     | Windows: `C:\Program Files\Common Files\Native Instruments\Guitar Rig 7\Rack Presets` |
|              | macOS: `/Library/Application Support/Native Instruments/Guitar Rig 7/Rack Presets` |
| Format       | `.ngrr` binary preset files                               |
| Count        | ~1425 files                                               |
| Licence      | Native Instruments EULA                                   |

### Guitar Rig 7 manual PDF (gitignored)

| Field         | Detail                                                   |
|--------------|----------------------------------------------------------|
| Source       | Native Instruments                                        |
| Download     | [Guitar_Rig_7_Manual_English_07_09_23.pdf](https://www.native-instruments.com/fileadmin/ni_media/downloads/manuals/gr7/Guitar_Rig_7_Manual_English_07_09_23.pdf) |
| Save to      | `data/external/Guitar_Rig_7_Manual_English_07_09_23.pdf`  |
| Used by      | `scripts/build_manual_chunks.py`                          |

### Blank_template.ngrr (committed)

An empty Guitar Rig 7 rack preset used as a binary template for
`ngrr_builder.transplant_preset()`. Created by saving an empty rack in GR7.

### crp_enum_lookup.json (committed)

Hand-curated enum mapping for Control Room Pro parameters: 31 cabinets
(0–30), 5 microphones (0–4), and 3 mic positions (0–2). Derived from
observation of the Guitar Rig 7 Control Room Pro UI. Cabinet naming
informed by [Ali Jamieson's hardware equivalencies](https://alijamieson.co.uk/2022/12/29/guitar-rig-6-equivalencies-updated-for-2022/).
Cannot be regenerated from code — this is manually maintained reference data.

### tonal_descriptors.json (committed)

Hand-curated vocabulary of tonal descriptor terms used by the modifier UI
chips in the Streamlit app. Manually maintained reference data.

---

## Pipeline-generated files (gitignored)

All produced by build scripts in `scripts/` and stored in `data/processed/`:

| File                         | Producing script                        |
|-----------------------------|-----------------------------------------|
| `component_schema.json`     | `build_component_schema.py`             |
| `tag_catalogue.json`        | `build_tag_catalogue.py`                |
| `gr_manual_chunks.json`     | `build_manual_chunks.py`                |
| `exemplar_store.json`       | `build_exemplar_index.py`               |
| `amp_cabinet_lookup.json`   | `build_amp_cabinet_lookup.py`           |
| `parameter_annotations.json`| `build_parameter_annotations.py`        |
| `chromadb/`                 | `build_retrieval_index.py` + `build_exemplar_index.py` |

---

## Reproducing from scratch

After setting `GR7_PRESETS_DIR` in `.env` and downloading the manual PDF:

```bash
uv run python scripts/build_component_schema.py
uv run python scripts/build_tag_catalogue.py
uv run python scripts/build_manual_chunks.py
uv run python scripts/build_retrieval_index.py
uv run python scripts/build_exemplar_index.py
uv run python scripts/build_amp_cabinet_lookup.py
uv run python scripts/build_crp_lookup.py
uv run python scripts/build_parameter_annotations.py
uv run python scripts/check_pipeline.py
```

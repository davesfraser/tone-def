# Data

This directory holds all data for **ToneDef**.

It is structured to separate data by stage of processing.
Raw inputs are treated as read-only. Processed outputs are derived and reproducible from raw.

---

## Directory structure

| Directory    | Purpose                                              |
|-------------|------------------------------------------------------|
| `raw/`      | Original source data — never modified after download |
| `interim/`  | Partially processed or filtered working files        |
| `processed/`| Clean, analysis-ready outputs from the pipeline      |
| `external/` | Third-party reference data or downloaded resources   |

Data files are gitignored. The folder structure is version-controlled via `.gitkeep` files.

---

## Data sources

Document each dataset below when you add it to the project.
This is the record that lets someone reproduce the analysis from scratch.

### [Dataset name]

| Field          | Detail                                     |
|---------------|--------------------------------------------|
| Source        | Where the data came from (URL, system, team) |
| Access        | How to obtain it (download link, API, request process) |
| Version/date  | The snapshot date or version identifier    |
| Licence       | Usage rights or data sharing agreement     |
| Added by      | Who added it and when                      |
| Raw file(s)   | Filename(s) as stored in `raw/`            |
| Notes         | Any known issues, caveats, or quirks       |

---

## Reproducing the data

Describe the steps to go from raw data to processed data.
If there is a pipeline script, reference it here.
```bash
# Example — replace with the actual command for this project
uv run python src/tonedef/pipeline.py
```

If raw data cannot be shared or re-downloaded freely, document the manual steps
needed to obtain it and where to request access.

---

## Data size and storage

Large files should not be committed to git.
If the project needs shared data access, document the approach here:
- Shared network drive path
- Cloud storage bucket and access instructions
- DVC remote (if adopted later)

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    """Return the absolute path to the checked-out project root.

    This template assumes code runs from a checked-out project repository.
    """
    # This file lives at src/<package>/paths.py, so three levels up is the root.
    return Path(__file__).resolve().parents[2]


# Path constants for every folder the template creates
# Import these directly rather than rebuilding paths from strings throughout
# your code — it keeps things consistent and easy to refactor
#
# Example:
#   from {{ package_name }}.paths import DATA_RAW, MODELS_DIR
#   df = pd.read_parquet(DATA_RAW / "survey_2024.parquet")

DATA_DIR = project_root() / "data"
DATA_RAW = DATA_DIR / "raw"  # original inputs — treat as read-only
DATA_INTERIM = DATA_DIR / "interim"  # partially processed
DATA_PROCESSED = DATA_DIR / "processed"  # clean, analysis-ready outputs
DATA_EXTERNAL = DATA_DIR / "external"  # third-party / downloaded data

OUTPUT_PRESETS = DATA_PROCESSED / "output_presets"  # generated .ngrr presets

MODELS_DIR = project_root() / "models"  # serialised models and artefacts
FIGURES_DIR = project_root() / "reports" / "figures"  # generated plots and charts
NOTEBOOKS_DIR = project_root() / "notebooks"  # useful if scripts need to reference notebooks

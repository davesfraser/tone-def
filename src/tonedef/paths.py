from __future__ import annotations

import warnings
from pathlib import Path

from tonedef.settings import settings


def project_root() -> Path:
    """Return the absolute path to the checked-out project root.

    This template assumes code runs from a checked-out project repository.
    """
    # This file lives at src/<package>/paths.py, so three levels up is the root.
    return Path(__file__).resolve().parents[2]


PACKAGE_DIR = Path(__file__).resolve().parent
PROMPT_TEMPLATES_DIR = PACKAGE_DIR / "prompt_templates"

# Path constants for every folder the template creates
# Import these directly rather than rebuilding paths from strings throughout
# your code — it keeps things consistent and easy to refactor
#
# Example:
#   from tonedef.paths import DATA_RAW, MODELS_DIR
#   df = pd.read_parquet(DATA_RAW / "survey_2024.parquet")

DATA_DIR = project_root() / "data"
DATA_RAW = DATA_DIR / "raw"  # original inputs — treat as read-only
DATA_INTERIM = DATA_DIR / "interim"  # partially processed
DATA_PROCESSED = DATA_DIR / "processed"  # clean, analysis-ready outputs
DATA_EXTERNAL = DATA_DIR / "external"  # third-party / downloaded data

EVALS_DIR = project_root() / "evals"
EVALS_DATASETS_DIR = EVALS_DIR / "datasets"
EVALS_GOLDEN_DIR = EVALS_DIR / "golden"
EVALS_RESULTS_DIR = EVALS_DIR / "results"

INDEXES_DIR = project_root() / "indexes"
TRACES_DIR = project_root() / "traces"
CACHE_DIR = project_root() / "cache"

# Canonical path for GR7 factory presets, configurable via GR7_PRESETS_DIR.
GR7_PRESETS_DIR = (
    Path(settings.gr7_presets_dir) if settings.gr7_presets_dir else DATA_EXTERNAL / "presets"
)

_OUTPUT_PRESETS_REMOVAL = "2026-07-01"


def __getattr__(name: str) -> Path:
    """Provide deprecated module attributes with warnings.

    `OUTPUT_PRESETS` is retained as a legacy alias for one deprecation window.
    """
    if name == "OUTPUT_PRESETS":
        warnings.warn(
            "`OUTPUT_PRESETS` is deprecated and will be removed after "
            f"{_OUTPUT_PRESETS_REMOVAL}; use `GR7_PRESETS_DIR` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return GR7_PRESETS_DIR
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


MODELS_DIR = project_root() / "models"  # serialised models and artefacts
FIGURES_DIR = project_root() / "reports" / "figures"  # generated plots and charts
NOTEBOOKS_DIR = project_root() / "notebooks"  # useful if scripts need to reference notebooks

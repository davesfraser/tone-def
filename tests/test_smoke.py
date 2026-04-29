import warnings
from pathlib import Path

import tonedef.paths as paths
from tonedef import __version__
from tonedef.paths import (
    CACHE_DIR,
    DATA_DIR,
    DATA_EXTERNAL,
    DATA_INTERIM,
    DATA_PROCESSED,
    DATA_RAW,
    EVALS_DATASETS_DIR,
    EVALS_DIR,
    EVALS_GOLDEN_DIR,
    EVALS_RESULTS_DIR,
    FIGURES_DIR,
    GR7_PRESETS_DIR,
    INDEXES_DIR,
    MODELS_DIR,
    NOTEBOOKS_DIR,
    PROMPT_TEMPLATES_DIR,
    TRACES_DIR,
    project_root,
)
from tonedef.settings import settings


def test_version_resolves() -> None:
    assert isinstance(__version__, str)
    assert __version__ != "0.0.0+unknown", (
        "Version is the fallback sentinel — run `uv sync` to install the package"
    )


def test_project_root_exists() -> None:
    assert project_root().is_dir()


def test_settings_loads() -> None:
    # Verify settings initialises without errors and returns typed values
    assert settings.environment in {"development", "production"}
    assert isinstance(settings.gr7_presets_dir, str)
    assert isinstance(settings.anthropic_api_key.get_secret_value(), str)
    assert settings.provider_primary == "anthropic"
    assert settings.default_model.startswith("anthropic/")
    assert settings.max_tokens >= 1
    assert settings.request_timeout_seconds > 0
    assert settings.retry_max_attempts >= 1
    assert isinstance(settings.cache_enabled, bool)
    assert settings.trace_backend == "none"
    assert 0.0 <= settings.phase1_temperature <= 2.0
    assert 0.0 <= settings.phase2_temperature <= 2.0


def test_all_path_constants_are_paths_under_root() -> None:
    root = project_root()
    constants = [
        DATA_DIR,
        DATA_EXTERNAL,
        DATA_INTERIM,
        DATA_PROCESSED,
        DATA_RAW,
        EVALS_DATASETS_DIR,
        EVALS_DIR,
        EVALS_GOLDEN_DIR,
        FIGURES_DIR,
        MODELS_DIR,
        NOTEBOOKS_DIR,
        PROMPT_TEMPLATES_DIR,
    ]

    for p in constants:
        assert isinstance(p, Path), f"Expected Path, got {type(p)}"
        assert p.is_relative_to(root), (
            f"{p.name} is not under the project root — "
            "paths.py and the folder layout may be out of sync"
        )
        # Verify the directory actually exists on disk, not just that the
        # path string is correctly formed — catches drift between paths.py
        # and the folders the template creates
        assert p.exists(), (
            f"{p.name} does not exist on disk — "
            "a directory may be missing from the template or paths.py "
            "references a folder that was never created"
        )


def test_dormant_artifact_path_constants_are_under_root() -> None:
    root = project_root()
    constants = [
        CACHE_DIR,
        EVALS_RESULTS_DIR,
        INDEXES_DIR,
        TRACES_DIR,
    ]

    for p in constants:
        assert isinstance(p, Path), f"Expected Path, got {type(p)}"
        assert p.is_relative_to(root)


def test_gr7_presets_path_alias_points_to_same_location() -> None:
    assert isinstance(GR7_PRESETS_DIR, Path)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        legacy_alias = paths.OUTPUT_PRESETS

    assert legacy_alias == GR7_PRESETS_DIR
    assert any("deprecated" in str(w.message).lower() for w in caught)

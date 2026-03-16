from pathlib import Path

from tonedef import __version__
from tonedef.paths import (
    DATA_DIR,
    DATA_EXTERNAL,
    DATA_INTERIM,
    DATA_PROCESSED,
    DATA_RAW,
    FIGURES_DIR,
    MODELS_DIR,
    NOTEBOOKS_DIR,
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
    assert isinstance(settings.alpha, float)
    assert isinstance(settings.min_sample_size, int)
    assert settings.environment in {"development", "production"}


def test_all_path_constants_are_paths_under_root() -> None:
    root = project_root()
    constants = [
        DATA_DIR,
        DATA_EXTERNAL,
        DATA_INTERIM,
        DATA_PROCESSED,
        DATA_RAW,
        FIGURES_DIR,
        MODELS_DIR,
        NOTEBOOKS_DIR,
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

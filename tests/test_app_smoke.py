"""Smoke tests for the Streamlit application layer.

These verify that the UI package and app-level dependencies resolve,
and that key constants/helpers used by app.py are correctly defined.
No Streamlit server or API key required.
"""

from __future__ import annotations

import ast
import importlib

from tonedef.paths import project_root

_APP_PY = project_root() / "app.py"


def test_ui_package_importable() -> None:
    """The ui package imports without error when Streamlit is installed."""
    ui = importlib.import_module("ui")
    assert hasattr(ui, "inject_css")
    assert hasattr(ui, "render_stepper")
    assert hasattr(ui, "render_tone_overview")
    assert hasattr(ui, "render_component_card")


def test_example_queries_non_empty() -> None:
    """EXAMPLE_QUERIES has at least one entry for the landing page."""
    from ui.components import EXAMPLE_QUERIES

    assert len(EXAMPLE_QUERIES) >= 1
    assert all(isinstance(q, str) and q.strip() for q in EXAMPLE_QUERIES)


def test_modification_colours_cover_all_states() -> None:
    """Every Phase 2 modification state has a colour assigned."""
    from ui.components import MODIFICATION_COLOURS

    expected = {"unchanged", "adjusted", "swapped", "added"}
    assert set(MODIFICATION_COLOURS.keys()) == expected


def test_confidence_dot_cover_all_levels() -> None:
    """Every provenance level has a dot emoji assigned."""
    from ui.components import CONFIDENCE_DOT

    expected = {"documented", "inferred", "estimated"}
    assert set(CONFIDENCE_DOT.keys()) == expected


def test_app_module_parses_as_valid_python() -> None:
    """app.py is syntactically valid Python (catches merge conflicts, encoding)."""
    source = _APP_PY.read_text(encoding="utf-8")
    ast.parse(source, filename="app.py")


def test_app_defaults_defined_in_source() -> None:
    """_DEFAULTS dict in app.py contains all expected session state keys.

    Uses AST parsing to inspect the dict without triggering Streamlit
    module-level side effects.
    """
    source = _APP_PY.read_text(encoding="utf-8")
    tree = ast.parse(source, filename="app.py")

    # Find the _DEFAULTS assignment (may be Assign or AnnAssign with type hint)
    defaults_keys: set[str] = set()
    for node in ast.walk(tree):
        target_name: str | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id == "_DEFAULTS":
                target_name = t.id
                value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "_DEFAULTS":
                target_name = node.target.id
                value = node.value

        if target_name and isinstance(value, ast.Dict):
            for key in value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    defaults_keys.add(key.value)

    expected = {
        "query",
        "selected_modifiers",
        "signal_chain_raw",
        "signal_chain_parsed",
        "phase1_validation",
        "build_validation",
        "components",
        "exemplars",
        "llm_usage_summary",
        "preset_bytes",
        "preset_name",
        "processing",
        "_last_built_name",
    }
    assert defaults_keys == expected, (
        f"Missing: {expected - defaults_keys}, Extra: {defaults_keys - expected}"
    )


def test_style_css_exists() -> None:
    """The CSS file referenced by the UI package exists on disk."""
    assert (project_root() / "ui" / "style.css").is_file()


def test_app_blocks_preset_build_on_validation_errors() -> None:
    """The Streamlit flow gates preset export when pre-build validation fails."""
    source = _APP_PY.read_text(encoding="utf-8")
    assert "_validate_components_for_build" in source
    assert "_has_blocking_validation_errors" in source
    assert "Preset file blocked" in source
    assert "st.stop()" in source

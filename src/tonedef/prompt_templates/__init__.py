from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from tonedef.paths import PROMPT_TEMPLATES_DIR


@dataclass(frozen=True)
class PromptMeta:
    """Metadata parsed from a prompt template header."""

    name: str
    path: Path
    title: str
    version: str
    eval_metric: str
    last_modified: str


def _prompt_path(name: str) -> Path:
    candidate = PROMPT_TEMPLATES_DIR / f"{name}.jinja"
    if not candidate.is_file():
        msg = f"Prompt template not found: {name}"
        raise FileNotFoundError(msg)
    return candidate


def _split_header(text: str) -> tuple[str, str]:
    if not text.startswith("{#"):
        return "", text

    end = text.find("#}")
    if end == -1:
        return "", text

    header = text[2:end]
    body = text[end + 2 :]
    return header, body


def load_prompt_source(name: str) -> str:
    """Load prompt source text, excluding the metadata header."""
    path = _prompt_path(name)
    _, body = _split_header(path.read_text(encoding="utf-8"))
    return body


def render_prompt(name: str, **context: object) -> str:
    """Render a prompt template with strict Jinja variable handling."""
    environment = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)
    template = environment.from_string(load_prompt_source(name))
    return template.render(**context)


def prompt_meta(name: str) -> PromptMeta:
    """Return lightweight metadata for a prompt template."""
    path = _prompt_path(name)
    header, _ = _split_header(path.read_text(encoding="utf-8"))
    fields: dict[str, str] = {}
    for line in header.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().lower()] = value.strip()

    return PromptMeta(
        name=name,
        path=path,
        title=fields.get("title", "unknown"),
        version=fields.get("version", "unknown"),
        eval_metric=fields.get("eval_metric", "unknown"),
        last_modified=fields.get("last_modified", "unknown"),
    )

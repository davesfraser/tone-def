# applied-skills: ds-workflow
"""Pipeline validation functions.

Each ``validate_*`` function is **pure** — no side-effects, no logging.
Callers decide how to surface the results (callouts, warnings, logs).

``ValidationResult`` is a plain dataclass that accumulates errors and warnings.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tonedef.models import ComponentOutput, validate_component_against_schema
from tonedef.signal_chain_parser import ParsedSignalChain

# Component names that serve as a cabinet solution in the signal chain.
_CABINET_SOLUTION_NAMES: frozenset[str] = frozenset(
    {
        "Control Room",
        "Control Room Pro",
        "Matched Cabinet Pro",
    }
)


def _is_cabinet_solution(name: str) -> bool:
    """Return True if *name* is a cabinet or control room component."""
    return name in _CABINET_SOLUTION_NAMES or "cabinet" in name.lower()


_VALID_CHAIN_TYPES = {"AMP_ONLY", "FULL_PRODUCTION"}


@dataclass
class ValidationResult:
    """Accumulator for validation errors and warnings."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """``True`` when there are no errors (warnings are acceptable)."""
        return len(self.errors) == 0

    def __str__(self) -> str:
        parts: list[str] = []
        if self.errors:
            parts.append(f"Errors ({len(self.errors)}):")
            parts.extend(f"  ✗ {e}" for e in self.errors)
        if self.warnings:
            parts.append(f"Warnings ({len(self.warnings)}):")
            parts.extend(f"  ⚠ {w}" for w in self.warnings)
        if not parts:
            parts.append("✓ No issues found")
        return "\n".join(parts)

    def merge(self, other: ValidationResult) -> ValidationResult:
        """Return a new result combining errors/warnings from both."""
        return ValidationResult(
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
        )


# ---------------------------------------------------------------------------
# Phase 1 validation
# ---------------------------------------------------------------------------


def validate_phase1(parsed: ParsedSignalChain) -> ValidationResult:
    """Validate the structured output of Phase 1 (signal chain parser).

    Args:
        parsed: The ``ParsedSignalChain`` to validate.

    Returns:
        ``ValidationResult`` with errors and warnings.
    """
    result = ValidationResult()

    # chain_type
    if not parsed.chain_type:
        result.errors.append("Could not determine the signal chain type")
    elif parsed.chain_type not in _VALID_CHAIN_TYPES:
        result.errors.append(f"Unrecognised chain type: {parsed.chain_type}")

    # sections / units
    if not parsed.sections:
        result.errors.append("No signal chain sections were found in the response")
    else:
        total_units = sum(len(s.units) for s in parsed.sections)
        if total_units == 0:
            result.errors.append("No gear was identified in the signal chain")

        for section in parsed.sections:
            for unit in section.units:
                if not unit.name:
                    result.errors.append(f"A component in the {section.title} section has no name")
                if not unit.unit_type:
                    result.errors.append(
                        f"{unit.name} in the {section.title} section has no type specified"
                    )

    # Warnings
    if parsed.chain_type == "FULL_PRODUCTION":
        cab_titles = {s.title for s in parsed.sections}
        if "Cabinet And Mic" not in cab_titles:
            result.warnings.append(
                "Full production chain is missing a cabinet and microphone section"
            )

    if not parsed.tags_characters and not parsed.tags_genres:
        result.warnings.append("No genre or character tags were detected for this tone")

    return result


# ---------------------------------------------------------------------------
# Retrieval validation
# ---------------------------------------------------------------------------


def validate_retrieval(
    exemplars: list[dict],
    min_score: float = 0.1,
) -> ValidationResult:
    """Validate exemplar retrieval quality.

    Args:
        exemplars: List of exemplar dicts (each has a ``distance`` field
            where ``score = 1 - distance``).
        min_score: Minimum acceptable score for the top exemplar.

    Returns:
        ``ValidationResult`` with warnings about poor retrieval.
    """
    result = ValidationResult()

    if not exemplars:
        result.warnings.append("No similar factory presets were found")
        return result

    best_score = 1.0 - exemplars[0].get("distance", 1.0)
    if best_score < min_score:
        result.warnings.append(
            f"The closest factory preset match was weak (score: {best_score:.3f})"
        )

    return result


# ---------------------------------------------------------------------------
# Phase 2 validation
# ---------------------------------------------------------------------------


def validate_phase2(
    components: list[ComponentOutput],
    schema: dict,
) -> ValidationResult:
    """Validate Phase 2 component list against the schema.

    Hard errors (unknown name/ID/param_id) come from
    ``validate_component_against_schema``.  Soft warnings flag param
    values outside the observed [min, max] range.

    Args:
        components: Parsed ``ComponentOutput`` instances.
        schema: Parsed ``component_schema.json``.

    Returns:
        ``ValidationResult`` with errors and warnings.
    """
    result = ValidationResult()

    if not components:
        result.errors.append("No components were generated for the preset")
        return result

    for comp in components:
        # Hard errors from schema check
        schema_errors = validate_component_against_schema(comp, schema)
        result.errors.extend(schema_errors)

        # Soft warnings: param values outside observed range
        name = comp.component_name
        if name in schema:
            param_lookup = {p["param_id"]: p for p in schema[name].get("parameters", [])}
            for pid, val in comp.parameters.items():
                if pid in param_lookup:
                    stats = param_lookup[pid].get("stats", {})
                    lo = stats.get("min", 0.0)
                    hi = stats.get("max", 1.0)
                    if val < lo or val > hi:
                        result.warnings.append(
                            f"{name}.{pid} = {val} outside observed range [{lo}, {hi}]"
                        )

    return result


# ---------------------------------------------------------------------------
# Signal chain order validation
# ---------------------------------------------------------------------------


def validate_signal_chain_order(
    components: list[ComponentOutput],
    amp_cabinet_lookup: dict[str, dict],
) -> ValidationResult:
    """Validate ordering constraints in the component list.

    Args:
        components: Ordered list of ``ComponentOutput`` instances.
        amp_cabinet_lookup: Amp-to-cabinet lookup table.

    Returns:
        ``ValidationResult`` with errors and warnings.
    """
    result = ValidationResult()
    amp_names_lower = {k.lower() for k in amp_cabinet_lookup}

    amp_idx: int | None = None
    cab_idx: int | None = None

    for idx, comp in enumerate(components):
        cname_lower = comp.component_name.lower()
        if cname_lower in amp_names_lower:
            amp_idx = idx
        if _is_cabinet_solution(comp.component_name):
            cab_idx = idx

    if amp_idx is None:
        result.errors.append("No amplifier was found in the signal chain")

    if cab_idx is None:
        result.warnings.append("No cabinet component was included in the signal chain")

    if amp_idx is not None and cab_idx is not None and cab_idx < amp_idx:
        result.warnings.append("The cabinet appears before the amplifier — this may cause issues")

    return result


# ---------------------------------------------------------------------------
# Pre-build validation
# ---------------------------------------------------------------------------


def validate_pre_build(
    components: list[ComponentOutput],
) -> ValidationResult:
    """Final validation before XML build.

    Args:
        components: The complete ordered component list.

    Returns:
        ``ValidationResult`` with errors and warnings.
    """
    result = ValidationResult()

    if not components:
        result.errors.append("No components to build — the preset is empty")
        return result

    names = [c.component_name for c in components]
    ids = [c.component_id for c in components]

    has_cab = any(_is_cabinet_solution(n) for n in names)
    if not has_cab:
        result.errors.append(
            "Missing cabinet component — the preset may not load correctly in Guitar Rig"
        )

    # Duplicate component_ids (unusual but possible error)
    seen_ids: set[int] = set()
    for cid in ids:
        if cid in seen_ids:
            result.warnings.append(f"Duplicate component detected (ID {cid})")
        seen_ids.add(cid)

    return result

"""Generate non-blocking SQL diagnostics from parsed candidate and reference queries."""

from __future__ import annotations

from typing import Any

from .safety_v1 import inspect_sql


GRADER_ID = "sql.diagnostics.v1"


def diagnose_sql(candidate: str, reference: str, config: dict[str, Any]) -> dict[str, Any]:
    candidate_view = inspect_sql(candidate)
    reference_view = inspect_sql(reference)
    expected_sources = {value.upper() for value in config.get("expected_sources", reference_view.sources)}
    actual_sources = {value.upper() for value in candidate_view.sources}
    checks = [
        {
            "id": "source_selection",
            "status": "pass" if actual_sources == expected_sources else "fail",
            "actual": sorted(actual_sources),
            "expected": sorted(expected_sources),
        }
    ]
    normalized = " ".join(candidate.upper().split())
    rules = config.get("rules") or {}
    for diagnostic in config.get("declared", []):
        if diagnostic == "source_selection":
            continue
        rule = rules.get(diagnostic)
        if rule:
            all_of = [str(value).upper() for value in rule.get("all_of", [])]
            any_of = [str(value).upper() for value in rule.get("any_of", [])]
            passed = all(value in normalized for value in all_of) and (
                not any_of or any(value in normalized for value in any_of)
            )
            checks.append({
                "id": diagnostic,
                "status": "pass" if passed else "fail",
                "required_all": all_of,
                "required_any": any_of,
            })
        else:
            checks.append({
                "id": diagnostic,
                "status": "unknown",
                "reason": "This property is evaluated from result or trace evidence after SQL execution.",
            })
    return {"grader_id": GRADER_ID, "grader_version": "1", "checks": checks}

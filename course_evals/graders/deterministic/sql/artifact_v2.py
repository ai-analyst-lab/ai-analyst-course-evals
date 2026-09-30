"""V2.1 candidate CSV/executed-SQL consistency, not golden-reference grading.

Only empty CSV cells in declared non-string nullable columns represent SQL NULL.
The existing v2 comparator allows NULL unless nullable is explicitly false here.
Empty strings in string columns and textual NULL/NaN tokens are not coerced.
"""
from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path

from ..cross_artifact import csv_result
from .compare_v2 import compare_results


GRADER_VERSION = "2.1"
GRADER_ID = "artifact.matches_executed_sql.v2.1"
_NULLABLE_TYPES = {"number", "decimal", "integer", "boolean", "date", "timestamp"}


def compare_candidate_csv(executed, path: Path, config: dict) -> dict:
    roles = {"actual": "candidate_csv", "expected": "candidate_executed_sql"}
    try:
        candidate = csv_result(path)
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        return {
            "grader_id": GRADER_ID, "grader_version": GRADER_VERSION,
            "pass": 0, "status": "fail", "comparison_roles": roles,
            "mismatches": [{"code": "invalid_candidate_artifact", "reason": str(exc)}],
        }
    rules = {str(k).strip().lower(): v for k, v in config.get("columns", {}).items()}
    aliases = {str(k).strip().lower(): str(v).strip().lower()
               for k, v in config.get("aliases", {}).items()}
    names = [aliases.get(str(c["name"]).strip().lower(), str(c["name"]).strip().lower())
             for c in candidate.columns]
    nullable = [rules.get(n, {}).get("type") in _NULLABLE_TYPES
                and rules.get(n, {}).get("nullable", True) is True for n in names]
    candidate = replace(candidate, rows=tuple(
        tuple(None if i < len(nullable) and nullable[i] and value == "" else value
              for i, value in enumerate(row)) for row in candidate.rows
    ))
    # Both sides belong to the candidate. Invalid SQL output is also a non-pass,
    # never an invalid authoritative reference. Golden comparisons stay in v2.
    grade = compare_results(candidate, executed, config)
    grade.update(grader_id=GRADER_ID, grader_version=GRADER_VERSION,
                 comparison_roles=roles)
    if grade["status"] == "error":
        grade["status"] = "fail"
    return grade

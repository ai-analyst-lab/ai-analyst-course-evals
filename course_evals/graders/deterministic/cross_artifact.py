"""Compare tabular values repeated across submitted artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .sql.compare_v1 import compare_results
from .sql.execute_v1 import QueryResult


GRADER_ID = "artifact.cross_table.v1"


def csv_result(path: Path) -> QueryResult:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        names = reader.fieldnames or []
    return QueryResult(
        columns=tuple({"name": name, "type_code": "CSV"} for name in names),
        rows=tuple(tuple(row.get(name) for name in names) for row in rows),
        query_id=None,
        elapsed_ms=0,
        truncated=False,
    )


def json_table_result(path: Path, field: str) -> QueryResult:
    value = json.loads(path.read_text(encoding="utf-8"))
    rows: Any = value
    for part in field.split("."):
        rows = rows[part]
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"{path}:{field} must contain a list of objects")
    names = list(rows[0]) if rows else []
    return QueryResult(
        columns=tuple({"name": name, "type_code": "JSON"} for name in names),
        rows=tuple(tuple(row.get(name) for name in names) for row in rows),
        query_id=None,
        elapsed_ms=0,
        truncated=False,
    )


def grade_cross_table(left: QueryResult, right: QueryResult, config: dict[str, Any]) -> dict[str, Any]:
    result = compare_results(left, right, config)
    result["grader_id"] = GRADER_ID
    return result

"""Stable registry for reusable course graders."""

from __future__ import annotations

from .graders.deterministic.sql.compare_v1 import compare_results
from .graders.deterministic.sql.diagnostics_v1 import diagnose_sql
from .graders.deterministic.sql.safety_v1 import inspect_sql


GRADERS = {
    "sql.safety.v1": inspect_sql,
    "sql.result.scalar.v1": compare_results,
    "sql.result.keyed_table.v1": compare_results,
    "sql.result.multiset_table.v1": compare_results,
    "sql.result.ordered_table.v1": compare_results,
    "sql.diagnostics.v1": diagnose_sql,
}


def resolve(grader_id: str):
    try:
        return GRADERS[grader_id]
    except KeyError as exc:
        raise ValueError(f"unknown grader ID: {grader_id}") from exc

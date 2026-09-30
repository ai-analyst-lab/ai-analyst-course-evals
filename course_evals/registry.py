"""Stable registry for reusable course graders."""

from __future__ import annotations

from .graders.deterministic.sql.compare_v1 import compare_results
from .graders.deterministic.sql.compare_v2 import compare_results as compare_results_v2
from .graders.deterministic.sql.diagnostics_v1 import diagnose_sql
from .graders.deterministic.sql.safety_v1 import inspect_sql
from .graders.deterministic.sql.safety_v2 import inspect_sql as inspect_sql_v2


GRADERS = {
    "sql.safety.v1": inspect_sql,
    "sql.safety.v2": inspect_sql_v2,
    "sql.result.scalar.v1": compare_results,
    "sql.result.keyed_table.v1": compare_results,
    "sql.result.multiset_table.v1": compare_results,
    "sql.result.ordered_table.v1": compare_results,
    "sql.diagnostics.v1": diagnose_sql,
    **{f"sql.result.{mode}.v2": compare_results_v2 for mode in ("scalar", "keyed_table", "multiset_table", "ordered_table")},
}


def resolve(grader_id: str):
    try:
        return GRADERS[grader_id]
    except KeyError as exc:
        raise ValueError(f"unknown grader ID: {grader_id}") from exc

"""Parse Snowflake SQL and enforce the evaluation read-only boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sqlglot
from sqlglot import exp


GRADER_ID = "sql.safety.v1"
BLOCKED_NODES = (
    exp.Alter,
    exp.Command,
    exp.Create,
    exp.Delete,
    exp.Drop,
    exp.Insert,
    exp.Merge,
    exp.Update,
)


@dataclass(frozen=True)
class SqlSafetyResult:
    passed: bool
    statement_count: int
    statement_type: str | None
    sources: tuple[str, ...]
    functions: tuple[str, ...]
    violations: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "statement_count": self.statement_count,
            "statement_type": self.statement_type,
            "sources": list(self.sources),
            "functions": list(self.functions),
            "violations": list(self.violations),
        }


def _table_name(table: exp.Table) -> str:
    parts = [table.catalog, table.db, table.name]
    return ".".join(str(part).upper() for part in parts if part)


def _source_allowed(source: str, allowed_sources: list[str]) -> bool:
    source = source.upper()
    allowed = [value.upper() for value in allowed_sources]
    return any(source == item or source.endswith(f".{item}") for item in allowed)


def inspect_sql(
    sql: str,
    *,
    allowed_sources: list[str] | None = None,
    prohibited_functions: list[str] | None = None,
) -> SqlSafetyResult:
    violations: list[str] = []
    try:
        statements = [statement for statement in sqlglot.parse(sql, read="snowflake") if statement]
    except sqlglot.errors.ParseError as exc:
        return SqlSafetyResult(False, 0, None, (), (), (f"parse_error: {exc}",))

    if len(statements) != 1:
        violations.append(f"expected_one_statement: observed={len(statements)}")
    if not statements:
        return SqlSafetyResult(False, 0, None, (), (), tuple(violations))

    statement = statements[0]
    statement_type = type(statement).__name__
    if not isinstance(statement, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        violations.append(f"not_read_only_select: {statement_type}")
    for node_type in BLOCKED_NODES:
        if statement.find(node_type):
            violations.append(f"blocked_statement_node: {node_type.__name__}")

    cte_names = {str(cte.alias_or_name).upper() for cte in statement.find_all(exp.CTE)}
    sources = sorted(
        {
            _table_name(table)
            for table in statement.find_all(exp.Table)
            if str(table.name).upper() not in cte_names
        }
    )
    if allowed_sources is not None:
        for source in sources:
            if not _source_allowed(source, allowed_sources):
                violations.append(f"disallowed_source: {source}")

    functions = sorted(
        {
            str(function.sql_name()).upper()
            for function in statement.find_all(exp.Func)
            if function.sql_name()
        }
    )
    blocked_functions = {value.upper() for value in (prohibited_functions or [])}
    for function in functions:
        if function in blocked_functions:
            violations.append(f"prohibited_function: {function}")

    return SqlSafetyResult(
        passed=not violations,
        statement_count=len(statements),
        statement_type=statement_type,
        sources=tuple(sources),
        functions=tuple(functions),
        violations=tuple(violations),
    )

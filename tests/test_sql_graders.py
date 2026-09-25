from __future__ import annotations

from course_evals.graders.deterministic.sql.compare_v1 import compare_results
from course_evals.graders.deterministic.sql.execute_v1 import QueryResult
from course_evals.graders.deterministic.sql.safety_v1 import inspect_sql


def result(columns, rows, *, truncated=False):
    return QueryResult(
        columns=tuple({"name": name, "type_code": "TEST"} for name in columns),
        rows=tuple(tuple(row) for row in rows),
        query_id="test",
        elapsed_ms=1,
        truncated=truncated,
    )


KEYED = {
    "mode": "keyed_table",
    "keys": ["month"],
    "columns": {
        "month": {"type": "string"},
        "count": {"type": "integer"},
        "value": {"type": "decimal", "absolute_tolerance": 0.01},
    },
}


def test_different_queries_with_same_result_are_safe_and_comparable():
    first = inspect_sql("SELECT month, SUM(value) FROM DB.SCHEMA.ORDERS GROUP BY 1", allowed_sources=["DB.SCHEMA.ORDERS"])
    second = inspect_sql("WITH x AS (SELECT * FROM DB.SCHEMA.ORDERS) SELECT month, SUM(value) FROM x GROUP BY 1", allowed_sources=["DB.SCHEMA.ORDERS"])
    assert first.passed and second.passed
    left = result(["month", "count", "value"], [["2024-10", 2, 10.0]])
    right = result(["month", "count", "value"], [["2024-10", 2, 10.0]])
    assert compare_results(left, right, KEYED)["pass"] == 1


def test_keyed_table_ignores_row_order_and_applies_tolerance():
    left = result(["month", "count", "value"], [["2024-11", 3, 20.001], ["2024-10", 2, 10.0]])
    right = result(["month", "count", "value"], [["2024-10", 2, 10.0], ["2024-11", 3, 20.0]])
    assert compare_results(left, right, KEYED)["pass"] == 1


def test_keyed_table_rejects_duplicate_keys():
    left = result(["month", "count", "value"], [["2024-10", 2, 10.0], ["2024-10", 2, 10.0]])
    right = result(["month", "count", "value"], [["2024-10", 2, 10.0]])
    grade = compare_results(left, right, KEYED)
    assert grade["pass"] == 0
    assert any(item["code"] == "duplicate_keys" for item in grade["mismatches"])


def test_column_aliases_are_applied_before_missing_column_check():
    left = result(["period", "count", "value"], [["2024-10", 2, 10.0]])
    right = result(["month", "count", "value"], [["2024-10", 2, 10.0]])
    config = {**KEYED, "aliases": {"period": "month"}}
    assert compare_results(left, right, config)["pass"] == 1


def test_value_outside_tolerance_fails():
    left = result(["month", "count", "value"], [["2024-10", 2, 10.02]])
    right = result(["month", "count", "value"], [["2024-10", 2, 10.0]])
    grade = compare_results(left, right, KEYED)
    assert grade["pass"] == 0
    assert grade["mismatches"][0]["code"] == "value"


def test_null_does_not_equal_zero():
    left = result(["month", "count", "value"], [["2024-10", 2, None]])
    right = result(["month", "count", "value"], [["2024-10", 2, 0]])
    assert compare_results(left, right, KEYED)["pass"] == 0


def test_missing_and_extra_columns_are_distinct():
    left = result(["month", "count", "other"], [["2024-10", 2, "x"]])
    right = result(["month", "count", "value"], [["2024-10", 2, 10]])
    codes = {row["code"] for row in compare_results(left, right, KEYED)["mismatches"]}
    assert codes == {"missing_columns", "extra_columns"}


def test_multiset_preserves_duplicate_counts():
    config = {"mode": "multiset_table", "columns": {"value": {"type": "integer"}}}
    left = result(["value"], [[1], [1]])
    right = result(["value"], [[1]])
    assert compare_results(left, right, config)["pass"] == 0


def test_ordered_table_treats_order_as_meaningful():
    config = {"mode": "ordered_table", "columns": {"rank": {"type": "integer"}}}
    left = result(["rank"], [[1], [2]])
    right = result(["rank"], [[2], [1]])
    assert compare_results(left, right, config)["pass"] == 0


def test_truncated_result_cannot_pass():
    left = result(["month", "count", "value"], [["2024-10", 2, 10]], truncated=True)
    right = result(["month", "count", "value"], [["2024-10", 2, 10]])
    assert compare_results(left, right, KEYED)["pass"] == 0


def test_safety_rejects_write_and_multiple_statements():
    assert not inspect_sql("DELETE FROM DB.SCHEMA.ORDERS").passed
    assert not inspect_sql("SELECT 1; SELECT 2").passed


def test_safety_rejects_disallowed_source():
    grade = inspect_sql("SELECT * FROM OTHER.SCHEMA.SECRETS", allowed_sources=["DB.SCHEMA.ORDERS"])
    assert not grade.passed
    assert any(value.startswith("disallowed_source") for value in grade.violations)

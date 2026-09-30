from datetime import date
import pytest
from course_evals.graders.deterministic.sql.compare_v2 import compare_results
from course_evals.graders.deterministic.sql.execute_v1 import QueryResult


def table(names, rows):
    return QueryResult(columns=tuple({"name": n} for n in names), rows=tuple(map(tuple, rows)), query_id="test", elapsed_ms=0, truncated=False)


def scalar(actual, expected, rule):
    return compare_results(table(["value"], [[actual]]), table(["value"], [[expected]]), {"mode": "scalar", "columns": {"value": rule}})


@pytest.mark.parametrize("actual,rule", [(2.9, {"type": "integer"}), ("maybe", {"type": "boolean"}), ("2024-01-01oops", {"type": "date"}), ("NaN", {"type": "decimal"}), (float('inf'), {"type": "decimal"})])
def test_invalid_values_do_not_normalize_to_pass(actual, rule):
    grade = scalar(actual, 2 if rule["type"] != "date" else "2024-01-01", rule)
    assert grade["pass"] == 0
    assert any(x["code"] == "invalid_value" for x in grade["mismatches"])


def test_keys_normalized_and_tolerance_applied():
    config = {"mode": "keyed_table", "keys": ["day"], "columns": {"day": {"type": "date"}, "v": {"type": "decimal", "absolute_tolerance": .01}}}
    a = table(["DAY", "v"], [[date(2024, 1, 1), 2.001]])
    b = table(["day", "v"], [["2024-01-01", "2"]])
    assert compare_results(a, b, config)["pass"] == 1


def test_duplicate_columns_fail_even_when_values_match():
    grade = compare_results(table(["v", "V"], [[1, 1]]), table(["v"], [[1]]), {"mode": "scalar", "columns": {"v": {"type": "integer"}}})
    assert grade["pass"] == 0
    assert grade["mismatches"][0]["code"] == "duplicate_columns"


def test_ordered_tolerance_is_not_ignored():
    config = {"mode": "ordered_table", "columns": {"v": {"type": "decimal", "absolute_tolerance": .01}}}
    assert compare_results(table(["v"], [[1.001]]), table(["v"], [[1]]), config)["pass"] == 1


def test_multiset_preserves_duplicates():
    config = {"mode": "multiset_table", "columns": {"v": {"type": "integer"}}}
    assert not compare_results(table(["v"], [[1], [1]]), table(["v"], [[1]]), config)["pass"]


@pytest.mark.parametrize("config", [{"columns": {}}, {"mode": "keyed_table", "columns": {"v": {"type": "integer"}}}, {"mode": "multiset_table", "columns": {"v": {"type": "decimal", "absolute_tolerance": .01}}}])
def test_bad_configuration_fails_instead_of_false_pass(config):
    with pytest.raises(ValueError):
        compare_results(table(["v"], [[1]]), table(["v"], [[1]]), config)


def test_bad_reference_is_error_not_candidate_failure():
    assert scalar(2, "bad", {"type": "integer"})["status"] == "error"


def test_null_is_not_zero():
    assert scalar(None, 0, {"type": "decimal"})["pass"] == 0

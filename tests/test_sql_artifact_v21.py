from pathlib import Path

import pytest

from course_evals.grader import _grade_query_outputs
from course_evals.graders.deterministic.sql.artifact_v2 import compare_candidate_csv
from course_evals.graders.deterministic.sql.compare_v2 import compare_results
from course_evals.graders.deterministic.sql.execute_v1 import QueryResult


def table(value):
    return QueryResult(columns=({"name": "value"},), rows=((value,),),
                       query_id="offline", elapsed_ms=0, truncated=False)


def config(kind="decimal", **rule):
    return {"mode": "scalar", "columns": {"value": {"type": kind, **rule}}}


def artifact(tmp_path, text, executed, rule=None):
    path = tmp_path / "results.csv"
    path.write_text('value\n' + text + '\n')
    return compare_candidate_csv(table(executed), path, rule or config())


@pytest.mark.parametrize("kind", ["decimal", "number", "integer", "boolean", "date", "timestamp"])
def test_empty_typed_nullable_csv_cell_matches_sql_null(tmp_path, kind):
    # Quoted blank is a real row, unlike a blank CSV line.
    grade = artifact(tmp_path, '""', None, config(kind, nullable=True))
    assert grade["status"] == "pass"
    assert grade["grader_version"] == "2.1"
    assert grade["comparison_roles"]["actual"] == "candidate_csv"


def test_default_nullable_preserves_existing_v2_sql_null_semantics(tmp_path):
    assert artifact(tmp_path, '""', None)["pass"] == 1
    assert artifact(tmp_path, '""', 0)["status"] == "fail"


def test_explicit_nonnullable_does_not_accept_blank(tmp_path):
    grade = artifact(tmp_path, '""', None, config(nullable=False))
    assert grade["status"] == "fail"
    assert grade["mismatches"][0]["code"] == "invalid_value"


def test_empty_string_is_not_changed_to_null(tmp_path):
    assert artifact(tmp_path, '""', "", config("string"))["pass"] == 1
    assert artifact(tmp_path, '""', None, config("string"))["status"] == "fail"


@pytest.mark.parametrize("text", ["bad", "NULL", "None", "NaN", "Infinity", " "])
def test_invalid_candidate_tokens_are_failure_not_grader_error(tmp_path, text):
    grade = artifact(tmp_path, text, 2)
    assert grade["pass"] == 0
    assert grade["status"] == "fail"


def test_invalid_executed_candidate_is_failure_but_bad_golden_stays_error(tmp_path):
    assert artifact(tmp_path, "2", "bad")["status"] == "fail"
    assert compare_results(table(2), table("bad"), config())["status"] == "error"


def test_missing_candidate_artifact_is_nonpass(tmp_path):
    grade = compare_candidate_csv(table(2), tmp_path / "missing.csv", config())
    assert grade["status"] == "fail"
    assert grade["mismatches"][0]["code"] == "invalid_candidate_artifact"


def test_candidate_column_contract_failure_is_not_bad_reference(tmp_path):
    p = tmp_path / "results.csv"
    p.write_text('wrong\n2\n')
    assert compare_candidate_csv(table(2), p, config())["status"] == "fail"


def grade_pair(tmp_path, candidate, golden, csv_value):
    (tmp_path / "calculation.sql").write_text("SELECT NULL AS value FROM DB.SCHEMA.ORDERS")
    (tmp_path / "reference.sql").write_text("SELECT 2 AS value FROM DB.SCHEMA.ORDERS")
    (tmp_path / "results.csv").write_text('value\n' + csv_value + '\n')

    class Executor:
        def execute(self, sql):
            return table(candidate if "SELECT NULL" in sql else golden)

    grades = _grade_query_outputs(
        submission=tmp_path, case_root=tmp_path, run_root=tmp_path, manifest={},
        executor=Executor(), grading={"query_outputs": [{
            "output_id": "result", "submission_sql": "calculation.sql",
            "reference_sql": "reference.sql", "submitted_table": "results.csv",
            "allowed_sources": ["DB.SCHEMA.ORDERS"], "comparison_version": "2",
            "comparison": config(),
        }]},
    )[1]
    return [g for g in grades if g["grader_id"] != "sql.submission.standalone.v1"]


def test_abstention_csv_consistent_but_nonnull_reference_still_fails(tmp_path):
    grades = grade_pair(tmp_path, None, 2, '""')
    assert [(g["grader_id"], g["status"]) for g in grades] == [
        ("artifact.matches_executed_sql.v2.1", "pass"),
        ("sql.result.scalar.v2", "fail"),
    ]


def test_invalid_candidate_artifact_does_not_mask_valid_sql_comparison(tmp_path):
    grades = grade_pair(tmp_path, 2, 2, "bad")
    assert [g["status"] for g in grades] == ["fail", "pass"]


def test_real_invalid_reference_remains_grading_error(tmp_path):
    grades = grade_pair(tmp_path, 2, "bad", "2")
    assert [g["status"] for g in grades] == ["pass", "error"]

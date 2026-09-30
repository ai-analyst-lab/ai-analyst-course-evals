import pytest

from course_evals.grader import _grade_query_outputs
from course_evals.graders.deterministic.sql.execute_v1 import QueryResult
from course_evals.graders.deterministic.sql.standalone_v1 import inspect_standalone


@pytest.mark.parametrize("sql", [
    "SELECT ?", "SELECT :month", "SELECT $month",
    "WITH period AS (SELECT CAST(? AS DATE) AS d) SELECT * FROM period",
    "SELECT 1 WHERE 1 IN (SELECT ?)",
])
def test_ast_placeholders_fail_standalone_contract(sql):
    result = inspect_standalone(sql)
    assert result["status"] == "fail"
    assert result["mismatches"][0]["code"] == "unbound_parameter"


@pytest.mark.parametrize("sql", [
    "SELECT '?' AS value", 'SELECT 1 AS "?"',
    "SELECT ':month $month ?' AS value -- ? :bind $bind\n",
    "SELECT 1 /* ? :bind $bind */", "SELECT $$?$$ AS value",
])
def test_literals_identifiers_and_comments_are_not_parameters(sql):
    assert inspect_standalone(sql)["pass"] == 1


def grade(tmp_path, candidate, reference, executor):
    (tmp_path / "calculation.sql").write_text(candidate)
    (tmp_path / "reference.sql").write_text(reference)
    return _grade_query_outputs(
        submission=tmp_path, case_root=tmp_path, run_root=tmp_path, manifest={}, executor=executor,
        grading={"query_outputs": [{"output_id": "result", "submission_sql": "calculation.sql",
                  "reference_sql": "reference.sql", "allowed_sources": [], "comparison_version": "2",
                  "comparison": {"mode": "scalar", "columns": {"value": {"type": "integer"}}}}]},
    )[1]


def test_unbound_submission_never_calls_executor(tmp_path):
    class NoCalls:
        def execute(self, sql):
            raise AssertionError("Unbound candidate must fail before warehouse access")
    result = grade(tmp_path, "SELECT ? AS value", "SELECT 1 AS value", NoCalls())
    assert len(result) == 1
    assert result[0]["grader_id"] == "sql.submission.standalone.v1"
    assert result[0]["status"] == "fail"


def test_real_executor_failure_remains_error(tmp_path):
    class Broken:
        def execute(self, sql):
            raise RuntimeError("warehouse connection unavailable")
    result = grade(tmp_path, "SELECT 1 AS value", "SELECT 1 AS value", Broken())
    assert result[-1]["status"] == "error"
    assert "warehouse connection unavailable" in result[-1]["reason"]


def test_bad_reference_binding_remains_error(tmp_path):
    class ReferenceBroken:
        def execute(self, sql):
            if '?' in sql:
                raise RuntimeError("reference bind missing")
            return QueryResult(({"name": "value"},), ((1,),), "offline", 0, False)
    result = grade(tmp_path, "SELECT 1 AS value", "SELECT ? AS value", ReferenceBroken())
    assert result[0]["pass"] == 1
    assert result[-1]["status"] == "error"
    assert "reference bind missing" in result[-1]["reason"]

from __future__ import annotations

import json
from pathlib import Path

from course_evals.suite import build_suite_report, build_suite_report_from_cases


def test_focused_sql_reference_contains_eight_reviewable_cases():
    import yaml

    private_path = Path("focused-cases/session6-sql-development.yaml")
    private = yaml.safe_load(private_path.read_text(encoding="utf-8"))
    private_cases = {case["case_id"]: case for case in private["cases"]}
    assert len(private_cases) == 8
    assert all("expected" in case for case in private_cases.values())
    assert all("reproduction" in case for case in private_cases.values())


def _graded_run(root: Path, case_id: str, passed: int) -> Path:
    summary = {
        "run_id": root.name,
        "trial_id": f"{case_id}-t1",
        "case_id": case_id,
        "case_version": "1",
        "case_pass": passed,
        "output_contract": 1,
        "deterministic_accuracy": passed,
        "final_answer_judge": 1,
    }
    grade_root = root / "trials" / summary["trial_id"] / "grades"
    grade_root.mkdir(parents=True)
    (grade_root / "summary.json").write_text(json.dumps(summary) + "\n")
    return root


def test_suite_report_preserves_failures_and_slices(tmp_path):
    first = _graded_run(tmp_path / "run-one", "novamart-monthly-operating-review-001", 1)
    second = _graded_run(tmp_path / "run-two", "novamart-promotion-profitability-002", 0)
    output = tmp_path / "suite"
    report = build_suite_report(run_roots=[first, second], output_root=output, suite_id="test-suite")
    assert report["overall"] == {"attempted": 2, "passed": 1, "failed": 1, "accuracy": 0.5}
    assert report["slices"]["domain"]["operations"]["accuracy"] == 1.0
    assert report["slices"]["domain"]["marketing"]["accuracy"] == 0.0
    assert (output / "suite-report.json").is_file()
    assert (output / "suite-report.md").is_file()
    assert (output / "suite-report.html").is_file()
    html = (output / "suite-report.html").read_text(encoding="utf-8")
    markdown = (output / "suite-report.md").read_text(encoding="utf-8")
    assert "Every case" in html
    assert "Headline gates" in html
    assert "Slices" in html
    assert "deterministic accuracy" in html
    assert "## Headline gates" in markdown


def test_complete_suite_keeps_execution_errors_in_denominator(tmp_path):
    cases = [
        {
            "run_id": "run-one", "trial_id": "trial-one",
            "case_id": "novamart-monthly-operating-review-001", "case_version": "1",
            "case_pass": 1, "output_contract": 1, "deterministic_accuracy": 1,
            "final_answer_judge": 1, "status": "graded",
            "slices": {"domain": "operations", "complexity": "low"},
        },
        {
            "run_id": None, "trial_id": None,
            "case_id": "novamart-promotion-profitability-002", "case_version": "1",
            "case_pass": 0, "output_contract": 0, "deterministic_accuracy": 0,
            "final_answer_judge": 0, "status": "error",
            "slices": {"domain": "marketing", "complexity": "high"},
        },
    ]
    report = build_suite_report_from_cases(
        cases=cases,
        output_root=tmp_path / "suite",
        suite_id="complete-suite",
    )
    assert report["overall"] == {"attempted": 2, "passed": 1, "failed": 1, "accuracy": 0.5}
    assert report["gates"]["output_contract"]["attempted"] == 2
    assert report["cases"][1]["status"] == "error"

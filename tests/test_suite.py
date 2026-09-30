from __future__ import annotations

import json
import pytest
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
    second = _graded_run(tmp_path / "run-two", "novamart-promotion-returns-010", 0)
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


def test_nested_grader_error_is_not_reported_as_completed_numerical_grading(tmp_path):
    root = _graded_run(tmp_path/'run', 'novamart-monthly-operating-review-001', 0)
    grade = next(root.glob('trials/*/grades'))
    (grade/'sql-result-1.json').write_text(json.dumps({'status':'error','pass':0,'reason':'connection unavailable'}))
    report = build_suite_report(run_roots=[root], output_root=tmp_path/'report', suite_id='test')
    assert report['overall']['attempted'] == 1
    assert report['overall']['passed'] == 0
    assert report['cases'][0]['status'] == 'grading_error'
    assert report['grading_error_case_count'] == 1
    assert 'do not demonstrate a numerical error' in (tmp_path/'report/suite-report.md').read_text()


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


def test_sql_report_does_not_claim_full_analysis_or_judge_accuracy(tmp_path):
    case = {"case_id": "sql-one", "case_pass": 1, "output_contract": 1, "deterministic_accuracy": 1,
            "final_answer_judge": None, "evaluation_mode": "sql_results", "slices": {"domain": "support"}}
    report = build_suite_report_from_cases(cases=[case], output_root=tmp_path / 'sql', suite_id='sql')
    assert report['accuracy_label'] == 'SQL/result accuracy'
    assert 'final_answer_judge' not in report['gates']
    assert 'Not assessed' in (tmp_path / 'sql/suite-report.html').read_text()
    assert 'Provisional authoring results' in (tmp_path / 'sql/suite-report.html').read_text()
    assert 'Provisional authoring results' in (tmp_path / 'sql/suite-report.md').read_text()
    with pytest.raises(ValueError, match='do not combine'):
        build_suite_report_from_cases(cases=[case, {**case, 'case_id': 'full', 'evaluation_mode': 'full_analysis'}], output_root=tmp_path / 'mixed', suite_id='mixed')


def test_slices_follow_versioned_reference_and_private_coverage(tmp_path, monkeypatch):
    import yaml
    import course_evals.suite as module
    # Test version selection explicitly without retaining retired course cases.
    for version, domain in [('1', 'operations'), ('3', 'commerce')]:
        root = tmp_path/'cases/slice-version-fixture'/('v'+version)
        root.mkdir(parents=True)
        (root/'reference.yaml').write_text(yaml.safe_dump({
            'case_version': version, 'slices': {'domain': domain},
            'coverage': {'family': 'meaning', 'role': 'target'}}))
    # The unversioned reference allows testing a mismatched requested version.
    root = tmp_path/'cases/slice-version-fixture'
    (root/'reference.yaml').write_text((root/'v1/reference.yaml').read_text())
    monkeypatch.setattr(module, 'REPO_ROOT', tmp_path)
    new = module._case_slices('slice-version-fixture', '1')
    assert new['context_family'] == 'meaning'
    assert new['context_role'] == 'target'
    assert module._case_slices('slice-version-fixture', '3')['domain'] == 'commerce'
    assert module._case_slices('slice-version-fixture', '1')['domain'] == 'operations'
    with pytest.raises(ValueError, match='version'):
        module._case_slices('slice-version-fixture', '999')


def test_partial_suite_cannot_be_reported_as_final_accuracy(tmp_path):
    from course_evals.suite import grade_complete_suite_manifest
    path=tmp_path/'manifest.json'
    path.write_text(json.dumps({'status':'running','requested_case_count':48,'cases':[]}))
    with pytest.raises(ValueError, match='unfinished'):
        grade_complete_suite_manifest(manifest_path=path)

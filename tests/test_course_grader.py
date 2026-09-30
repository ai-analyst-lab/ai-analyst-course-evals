from __future__ import annotations

import json
import shutil
import copy
from pathlib import Path

import pytest

from course_evals.grader import digest_file, digest_payload, grade_run, verify_lock
from course_evals.graders.deterministic.sql.execute_v1 import QueryResult


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = REPO_ROOT / "cases" / "novamart-monthly-operating-review-001"
PROMOTION_CASE_ROOT = REPO_ROOT / "tests" / "fixtures" / "cases" / "novamart-promotion-profitability-002"


def test_sql_mode_grades_without_calling_model_judge(tmp_path, monkeypatch):
    import course_evals.grader as module
    run = build_run(tmp_path)
    manifest_path = run / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['evaluation_mode'] = 'sql_results'
    manifest_path.write_text(json.dumps(manifest))
    case_root, reference, grading = module.load_case('novamart-monthly-operating-review-001', '1')
    grading = copy.deepcopy(grading)
    grading.update(evaluation_mode='sql_results', model_graders=[], cross_artifact_tables=[])
    grading['query_outputs'][0]['comparison_version'] = '2'
    monkeypatch.setattr(module, 'load_case', lambda *args: (case_root, reference, grading))
    def no_judge(**kwargs):
        raise AssertionError('SQL/result mode must not call a model')
    summary = grade_run(run_root=run, judge=no_judge, sql_executor=FakeSqlExecutor())
    assert summary['case_pass'] == 1
    assert summary['final_answer_judge'] is None
    assert summary['evaluation_mode'] == 'sql_results'


def test_all_csv_grader_configs_have_required_identifiers():
    import yaml
    for path in (REPO_ROOT / 'cases').rglob('grading.yaml'):
        config = yaml.safe_load(path.read_text())
        for spec in config.get('artifact_contract', {}).get('csv', []):
            assert spec.get('id'), str(path)


def test_versioned_sql_cases_preserve_original_reference(tmp_path, monkeypatch):
    import yaml
    import course_evals.grader as module
    case_id = 'version-routing-fixture'
    for version in ('1', '2'):
        destination = tmp_path / 'cases' / case_id / ('v' + version)
        shutil.copytree(CASE_ROOT, destination)
        for name in ('reference.yaml', 'grading.yaml'):
            path = destination / name
            data = yaml.safe_load(path.read_text())
            data.update(case_id=case_id, case_version=version)
            path.write_text(yaml.safe_dump(data))
    monkeypatch.setattr(module, 'REPO_ROOT', tmp_path)
    root1, ref1, config1 = module.load_case(case_id, '1')
    root2, ref2, config2 = module.load_case(case_id, '2')
    assert root1 != root2
    assert ref1['case_version'] == '1' and ref2['case_version'] == '2'
    assert (root1 / 'reference.sql').read_bytes() == (root2 / 'reference.sql').read_bytes()
    assert config1['query_outputs'] == config2['query_outputs']


def test_generated_complete_cases_keep_reference_and_grader_together():
    generated = [
        path for path in (REPO_ROOT / "cases").glob("novamart-*")
        if path.name not in {
            "novamart-monthly-operating-review-001",
            "novamart-promotion-profitability-002",
            "novamart-quarterly-net-revenue-002",
        }
    ]
    assert len(generated) == 19
    for root in generated:
        reference = __import__("yaml").safe_load((root / "reference.yaml").read_text())
        grading = __import__("yaml").safe_load((root / "grading.yaml").read_text())
        assert reference["case_id"] == grading["case_id"] == root.name
        assert reference["expected"]["results"]
        assert (root / "reference.sql").read_text().strip().lower().startswith(("select", "with"))
        assert grading["query_outputs"][0]["comparison"]["mode"] == "keyed_table"


def test_low_direction_cases_use_lowest_in_judge_criteria():
    for case_id in (
        "novamart-nps-segment-004",
        "novamart-session-conversion-device-005",
        "novamart-device-funnel-019",
    ):
        reference = __import__("yaml").safe_load(
            (REPO_ROOT / "cases" / case_id / "reference.yaml").read_text()
        )
        conclusion = " ".join(reference["accepted_final_answer"]["required_conclusion"])
        assert "lowest observed" in conclusion
        assert "highest observed" not in conclusion


def test_membership_cancellation_reference_preserves_tied_headline():
    reference = __import__("yaml").safe_load(
        (
            REPO_ROOT
            / "cases"
            / "novamart-membership-cancellation-016"
            / "reference.yaml"
        ).read_text()
    )
    conclusion = " ".join(reference["accepted_final_answer"]["required_conclusion"])
    assert "tied for the highest observed" in conclusion
    assert "not_using" in conclusion
    assert "price" in conclusion


def build_run(tmp_path: Path, *, wrong_count: bool = False) -> Path:
    run_root = tmp_path / "analysis-eval-test"
    trial_id = "novamart-monthly-operating-review-001-t1-test"
    trial_root = run_root / "trials" / trial_id
    submission = trial_root / "submission"
    shutil.copytree(CASE_ROOT / "golden-output", submission)
    if wrong_count:
        result_path = submission / "result.json"
        result = json.loads(result_path.read_text())
        result["monthly_results"][0]["completed_order_count"] += 1
        result_path.write_text(json.dumps(result, indent=2) + "\n")
    files = [
        {"path": path.name, "sha256": digest_file(path), "bytes": path.stat().st_size}
        for path in sorted(submission.iterdir())
        if path.is_file()
    ]
    bundle_digest = digest_payload(files)
    (trial_root / "artifact-manifest.json").write_text(
        json.dumps({
            "run_id": run_root.name,
            "trial_id": trial_id,
            "case_id": "novamart-monthly-operating-review-001",
            "case_version": "1",
            "files": files,
            "bundle_digest": bundle_digest,
        }, indent=2) + "\n"
    )
    (trial_root / "trial.json").write_text(
        json.dumps({
            "run_id": run_root.name,
            "trial_id": trial_id,
            "case_id": "novamart-monthly-operating-review-001",
            "case_version": "1",
            "status": "locked",
            "artifact_bundle_digest": bundle_digest,
        }, indent=2) + "\n"
    )
    trace = trial_root / "trace"
    trace.mkdir()
    (trace / "manifest.json").write_text(
        json.dumps({
            "complete": False,
            "missing": ["trace_html"],
            "files": [],
            "bundle_digest": digest_payload([]),
        }, indent=2) + "\n"
    )
    trial_path = trial_root / "trial.json"
    trial = json.loads(trial_path.read_text())
    trial["trace_bundle_digest"] = digest_payload([])
    trial_path.write_text(json.dumps(trial, indent=2) + "\n")
    run_root.mkdir(exist_ok=True)
    (run_root / "manifest.json").write_text(
        json.dumps({
            "run_id": run_root.name,
            "case_id": "novamart-monthly-operating-review-001",
            "case_version": "1",
            "status": "locked",
            "data_snapshot": "novamart-orders-2026-09-21-v1",
            "data_fingerprint": {
                "status": "verified",
                "sha256": "e3878063bee620c1706f346d12ffbbec2665b5d50448102afa2ae22304ff1c2f",
            },
        }, indent=2) + "\n"
    )
    (run_root / "events.jsonl").write_text("")
    return run_root


def passing_judge(**kwargs):
    return {
        "grader_id": "final-answer-judge",
        "grader_version": "test",
        "model": "fake",
        "prompt_sha256": "fake",
        "pass": 1,
        "reason": "The conclusion and recommendation match the reviewed criteria.",
    }


class FakeSqlExecutor:
    def execute(self, sql: str) -> QueryResult:
        return QueryResult(
            columns=(
                {"name": "month", "type_code": "TEXT"},
                {"name": "completed_order_count", "type_code": "INTEGER"},
                {"name": "completed_order_value", "type_code": "DECIMAL"},
                {"name": "average_completed_order_value", "type_code": "DECIMAL"},
            ),
            rows=(
                ("2024-10", 4672, 381765.78, 81.71356592465754),
                ("2024-11", 6048, 441001.93, 72.91764781746032),
                ("2024-12", 6215, 453073.37, 72.89997908286404),
            ),
            query_id="fake-query",
            elapsed_ms=1,
            truncated=False,
        )


class FakePromotionSqlExecutor:
    def execute(self, sql: str) -> QueryResult:
        return QueryResult(
            columns=tuple(
                {"name": name, "type_code": "TEST"}
                for name in (
                    "promo_name", "start_date", "end_date", "promo_days",
                    "completed_order_count", "discounted_merchandise_value",
                    "merchandise_cost", "merchandise_gross_profit", "gross_profit_per_day",
                )
            ),
            rows=(
                ("Black Friday", "2024-11-25", "2024-12-01", 7, 2387, 117239.0, 86793.53, 30445.47, 4349.35),
                ("Holiday Sale", "2024-12-15", "2024-12-31", 17, 3520, 220071.05, 152784.6, 67286.45, 3958.03),
            ),
            query_id="fake-promotion-query",
            elapsed_ms=1,
            truncated=False,
        )


def build_promotion_run(tmp_path: Path) -> Path:
    run_root = tmp_path / "promotion-eval-test"
    trial_id = "novamart-promotion-profitability-002-t1-test"
    trial_root = run_root / "trials" / trial_id
    submission = trial_root / "submission"
    shutil.copytree(PROMOTION_CASE_ROOT / "golden-output", submission)
    files = [
        {"path": path.name, "sha256": digest_file(path), "bytes": path.stat().st_size}
        for path in sorted(submission.iterdir()) if path.is_file()
    ]
    bundle_digest = digest_payload(files)
    (trial_root / "artifact-manifest.json").write_text(json.dumps({
        "files": files, "bundle_digest": bundle_digest,
    }, indent=2) + "\n")
    trace = trial_root / "trace"
    trace.mkdir()
    trace_digest = digest_payload([])
    (trace / "manifest.json").write_text(json.dumps({
        "complete": False, "missing": ["trace_html"], "files": [], "bundle_digest": trace_digest,
    }, indent=2) + "\n")
    (trial_root / "trial.json").write_text(json.dumps({
        "run_id": run_root.name,
        "trial_id": trial_id,
        "case_id": "novamart-promotion-profitability-002",
        "case_version": "1",
        "status": "locked",
        "artifact_bundle_digest": bundle_digest,
        "trace_bundle_digest": trace_digest,
    }, indent=2) + "\n")
    run_root.mkdir(exist_ok=True)
    (run_root / "manifest.json").write_text(json.dumps({
        "run_id": run_root.name,
        "case_id": "novamart-promotion-profitability-002",
        "case_version": "1",
        "status": "locked",
        "data_fingerprint": {
            "status": "verified",
            "sha256": "fe3770e913305ffb1917a1b2e8eb1fd449773c78b58bb730aecfb6eaa821fa84",
        },
    }, indent=2) + "\n")
    (run_root / "events.jsonl").write_text("")
    return run_root


def test_golden_run_passes_and_writes_reports(tmp_path):
    run_root = build_run(tmp_path)
    summary = grade_run(run_root=run_root, judge=passing_judge, sql_executor=FakeSqlExecutor())
    assert summary["output_contract"] == 1
    assert summary["deterministic_accuracy"] == 1
    assert summary["final_answer_judge"] == 1
    assert summary["case_pass"] == 1
    trial_root = next((run_root / "trials").iterdir())
    assert (trial_root / "grades" / "summary.json").is_file()
    assert (trial_root / "student-report.md").is_file()
    assert (trial_root / "student-report.html").is_file()


def test_wrong_number_fails_accuracy(tmp_path):
    run_root = build_run(tmp_path, wrong_count=True)
    summary = grade_run(run_root=run_root, judge=passing_judge, sql_executor=FakeSqlExecutor())
    assert summary["output_contract"] == 1
    assert summary["deterministic_accuracy"] == 0
    assert summary["case_pass"] == 0


def test_second_case_uses_generic_grading_pipeline(tmp_path, monkeypatch):
    import course_evals.grader as module
    # Historical promotion output is a test fixture, not a student case.
    monkeypatch.setattr(module, 'REPO_ROOT', REPO_ROOT / 'tests' / 'fixtures')
    run_root = build_promotion_run(tmp_path)
    summary = grade_run(
        run_root=run_root,
        judge=passing_judge,
        sql_executor=FakePromotionSqlExecutor(),
    )
    assert summary["case_id"] == "novamart-promotion-profitability-002"
    assert summary["deterministic_accuracy"] == 1
    assert summary["case_pass"] == 1


def test_grader_rejects_changed_locked_artifact(tmp_path):
    run_root = build_run(tmp_path)
    trial_root = next((run_root / "trials").iterdir())
    result = trial_root / "submission" / "result.json"
    result.write_text(result.read_text() + " ")
    with pytest.raises(ValueError, match="locked artifact changed"):
        verify_lock(trial_root)


def test_grader_rejects_changed_locked_trace(tmp_path):
    run_root = build_run(tmp_path)
    trial_root = next((run_root / "trials").iterdir())
    trace_root = trial_root / "trace"
    trace_file = trace_root / "action_log.jsonl"
    trace_file.write_text('{"event":"query"}\n')
    trace_manifest_path = trace_root / "manifest.json"
    record = {"path": trace_file.name, "sha256": digest_file(trace_file), "bytes": trace_file.stat().st_size}
    trace_manifest = {"complete": True, "missing": [], "files": [record], "bundle_digest": digest_payload([record])}
    trace_manifest_path.write_text(json.dumps(trace_manifest, indent=2) + "\n")
    trial_path = trial_root / "trial.json"
    trial = json.loads(trial_path.read_text())
    trial["trace_bundle_digest"] = trace_manifest["bundle_digest"]
    trial_path.write_text(json.dumps(trial, indent=2) + "\n")

    trace_file.write_text('{"event":"changed"}\n')
    with pytest.raises(ValueError, match="locked trace artifact changed"):
        verify_lock(trial_root)


def test_grader_rejects_unverified_data_snapshot(tmp_path):
    run_root = build_run(tmp_path)
    manifest_path = run_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["data_fingerprint"] = {"status": "skipped"}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    with pytest.raises(ValueError, match="verified data snapshot"):
        grade_run(run_root=run_root, judge=passing_judge, sql_executor=FakeSqlExecutor())

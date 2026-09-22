from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from course_evals.grader import digest_file, digest_payload, grade_run, verify_lock


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = REPO_ROOT / "cases" / "novamart-monthly-operating-review-001"


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
        json.dumps({"complete": False, "missing": ["trace_html"]}, indent=2) + "\n"
    )
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


def test_golden_run_passes_and_writes_reports(tmp_path):
    run_root = build_run(tmp_path)
    summary = grade_run(run_root=run_root, judge=passing_judge)
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
    summary = grade_run(run_root=run_root, judge=passing_judge)
    assert summary["output_contract"] == 0
    assert summary["deterministic_accuracy"] == 0
    assert summary["case_pass"] == 0


def test_grader_rejects_changed_locked_artifact(tmp_path):
    run_root = build_run(tmp_path)
    trial_root = next((run_root / "trials").iterdir())
    result = trial_root / "submission" / "result.json"
    result.write_text(result.read_text() + " ")
    with pytest.raises(ValueError, match="locked artifact changed"):
        verify_lock(trial_root)


def test_grader_rejects_unverified_data_snapshot(tmp_path):
    run_root = build_run(tmp_path)
    manifest_path = run_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["data_fingerprint"] = {"status": "skipped"}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    with pytest.raises(ValueError, match="verified data snapshot"):
        grade_run(run_root=run_root, judge=passing_judge)

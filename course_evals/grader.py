"""Verify and grade a locked full-analysis run without changing its submission."""

from __future__ import annotations

import hashlib
import html
import importlib.util
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def student_safe_text(value: Any) -> str:
    return str(value).replace("\u2014", "-").replace("\u2013", "-")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return path


def digest_payload(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_trial(run_root: Path, trial_id: str | None) -> Path:
    trials_root = run_root / "trials"
    if trial_id:
        trial = trials_root / trial_id
        if not (trial / "trial.json").is_file():
            raise ValueError(f"trial does not exist: {trial_id}")
        return trial
    trials = sorted(path for path in trials_root.iterdir() if (path / "trial.json").is_file())
    if len(trials) != 1:
        raise ValueError("specify a trial ID when a run does not contain exactly one trial")
    return trials[0]


def verify_lock(trial_root: Path) -> tuple[dict[str, Any], Path]:
    trial = read_json(trial_root / "trial.json")
    if trial.get("status") != "locked":
        raise ValueError(f"course grading requires a locked trial, found {trial.get('status')}")
    artifact_manifest = read_json(trial_root / "artifact-manifest.json")
    submission = trial_root / "submission"
    observed = []
    expected_names = sorted(record["path"] for record in artifact_manifest["files"])
    actual_names = sorted(path.name for path in submission.iterdir() if path.is_file())
    if actual_names != expected_names:
        raise ValueError(f"locked submission file set changed: {actual_names}")
    for record in artifact_manifest["files"]:
        path = submission / record["path"]
        if not path.is_file():
            raise ValueError(f"locked artifact is missing: {record['path']}")
        actual = {"path": record["path"], "sha256": digest_file(path), "bytes": path.stat().st_size}
        if actual != record:
            raise ValueError(f"locked artifact changed: {record['path']}")
        observed.append(actual)
    bundle_digest = digest_payload(observed)
    if bundle_digest != artifact_manifest["bundle_digest"]:
        raise ValueError("artifact manifest bundle digest is invalid")
    if bundle_digest != trial.get("artifact_bundle_digest"):
        raise ValueError("trial bundle digest does not match the artifact manifest")
    return trial, submission


def load_case(case_id: str, case_version: str) -> tuple[Path, dict[str, Any]]:
    case_root = REPO_ROOT / "cases" / case_id
    reference_path = case_root / "reference.yaml"
    if not reference_path.is_file():
        raise ValueError(f"course reference is missing for {case_id}")
    reference = yaml.safe_load(reference_path.read_text(encoding="utf-8")) or {}
    if str(reference.get("case_version")) != str(case_version):
        raise ValueError(
            f"course reference version {reference.get('case_version')} does not match run version {case_version}"
        )
    return case_root, reference


def load_deterministic_grader(case_root: Path):
    path = case_root / "grade_submission.py"
    spec = importlib.util.spec_from_file_location(f"course_grade_{case_root.name}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load deterministic grader: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.grade


def run_llm_judge(
    *,
    case_root: Path,
    submission: Path,
    reference: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    contract_path = case_root / "final-answer-judge.md"
    contract = contract_path.read_text(encoding="utf-8")
    result = read_json(submission / "result.json")
    student_input = {
        "final_answer": result.get("final_answer"),
        "brief": (submission / "brief.md").read_text(encoding="utf-8"),
    }
    private_criteria = {
        "required_conclusion": reference["accepted_final_answer"]["required_conclusion"],
        "required_recommendation": reference["accepted_final_answer"]["required_recommendation"],
        "prohibited_claims": reference["accepted_final_answer"]["prohibited_claims"],
    }
    prompt = (
        contract
        + "\n\nREVIEWED PRIVATE CRITERIA:\n"
        + json.dumps(private_criteria, indent=2)
        + "\n\nSTUDENT OUTPUT:\n"
        + json.dumps(student_input, indent=2)
    )
    output_schema = {
        "type": "object",
        "properties": {
            "pass": {"type": "integer", "enum": [0, 1]},
            "reason": {"type": "string"},
        },
        "required": ["pass", "reason"],
        "additionalProperties": False,
    }
    with tempfile.TemporaryDirectory(prefix="ai-analyst-judge-") as workspace:
        command = [
            "claude",
            "--print",
            "--model",
            model,
            "--no-session-persistence",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(output_schema, separators=(",", ":")),
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--permission-mode",
            "dontAsk",
            "--permission-prompts",
            "none",
            "--tools=",
            "--allowedTools=",
            prompt,
        ]
        process = subprocess.run(
            command,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=180,
        )
    if process.returncode != 0:
        raise RuntimeError(f"final-answer judge failed: {process.stderr[-2000:]}")
    envelope = json.loads(process.stdout)
    verdict = envelope.get("structured_output")
    if not isinstance(verdict, dict) or verdict.get("pass") not in {0, 1}:
        raise ValueError("final-answer judge returned an invalid verdict")
    return {
        "grader_id": "final-answer-judge",
        "grader_version": "1",
        "model": model,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "contract_sha256": digest_file(contract_path),
        "pass": int(verdict["pass"]),
        "reason": student_safe_text(verdict["reason"]),
        "graded_at": utc_now(),
    }


def render_reports(trial_root: Path, summary: dict[str, Any]) -> None:
    gates = [
        ("Output contract", summary["output_contract"]),
        ("Deterministic accuracy", summary["deterministic_accuracy"]),
        ("Conclusion and recommendation", summary["final_answer_judge"]),
    ]
    lines = [
        f"# Evaluation report: {summary['case_id']}",
        "",
        f"**Overall result:** {'PASS' if summary['case_pass'] else 'FAIL'}",
        f"**Run:** `{summary['run_id']}`",
        f"**Trial:** `{summary['trial_id']}`",
        f"**Locked bundle:** `{summary['bundle_digest']}`",
        "",
        "| Gate | Result |",
        "|---|---:|",
    ]
    for label, value in gates:
        lines.append(f"| {label} | {'Pass' if value else 'Fail'} |")
    lines.extend(
        [
            "",
            "## Final-answer review",
            "",
            summary["judge_reason"],
            "",
            "## Diagnostic information",
            "",
            f"- Trace evidence complete: {'Yes' if summary['diagnostics']['trace_complete'] else 'No'}",
            f"- Missing trace evidence: {', '.join(summary['diagnostics']['missing_trace_evidence']) or 'None'}",
            "",
            "Read the individual grade records in `grades/` and the saved trace before changing the system.",
        ]
    )
    markdown = "\n".join(lines) + "\n"
    (trial_root / "student-report.md").write_text(markdown, encoding="utf-8")
    rows = "".join(
        f"<tr><td>{html.escape(label)}</td><td>{'Pass' if value else 'Fail'}</td></tr>"
        for label, value in gates
    )
    document = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Evaluation report</title><style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:40px;color:#1f2937}}
.card{{max-width:900px;border:1px solid #dbe3ea;border-radius:14px;padding:28px}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:10px;border-bottom:1px solid #e5e7eb;text-align:left}}
.pass{{color:#08775b}}.fail{{color:#b42318}}code{{font-size:12px}}
</style></head><body><div class="card"><h1>Evaluation report</h1>
<p class="{'pass' if summary['case_pass'] else 'fail'}"><strong>{'PASS' if summary['case_pass'] else 'FAIL'}</strong></p>
<p>Run <code>{html.escape(summary['run_id'])}</code></p>
<table><thead><tr><th>Gate</th><th>Result</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Final-answer review</h2><p>{html.escape(summary['judge_reason'])}</p>
<h2>Trace</h2><p>{'Complete' if summary['diagnostics']['trace_complete'] else 'Incomplete'}</p>
<p>Use the saved grade records and trace to diagnose the result before changing the system.</p>
</div></body></html>"""
    (trial_root / "student-report.html").write_text(document, encoding="utf-8")


def grade_run(
    *,
    run_root: str | Path,
    trial_id: str | None = None,
    judge_model: str = "claude-opus-4-6",
    judge: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    run_root = Path(run_root).resolve()
    manifest_path = run_root / "manifest.json"
    manifest = read_json(manifest_path)
    trial_root = resolve_trial(run_root, trial_id)
    grades_root = trial_root / "grades"
    if grades_root.exists() and any(grades_root.iterdir()):
        raise ValueError("this trial already has grade records; create a new run instead of overwriting them")
    trial, submission = verify_lock(trial_root)
    case_root, reference = load_case(trial["case_id"], trial["case_version"])
    data_fingerprint = manifest.get("data_fingerprint") or {}
    expected_data_fingerprint = reference["source"]["table_fingerprint"]["value"]
    if data_fingerprint.get("status") != "verified":
        raise ValueError("course grading requires a verified data snapshot fingerprint")
    if data_fingerprint.get("sha256") != expected_data_fingerprint:
        raise ValueError("run data fingerprint does not match the reviewed reference")
    deterministic_grade = load_deterministic_grader(case_root)
    deterministic = deterministic_grade(submission)

    judge_function = judge or run_llm_judge
    judge_result = judge_function(
        case_root=case_root,
        submission=submission,
        reference=reference,
        model=judge_model,
    )
    trace_manifest_path = trial_root / "trace" / "manifest.json"
    trace_manifest = read_json(trace_manifest_path) if trace_manifest_path.is_file() else {
        "complete": False,
        "missing": ["trace_manifest"],
    }
    output_contract = int(deterministic["output_contract"])
    deterministic_accuracy = int(deterministic["deterministic_accuracy"])
    final_answer_judge = int(judge_result["pass"])
    case_pass = int(output_contract and deterministic_accuracy and final_answer_judge)
    summary = {
        "schema_version": "1",
        "run_id": trial["run_id"],
        "trial_id": trial["trial_id"],
        "case_id": trial["case_id"],
        "case_version": trial["case_version"],
        "bundle_digest": trial["artifact_bundle_digest"],
        "reference_version": str(reference["case_version"]),
        "reference_review_status": reference.get("review_status"),
        "output_contract": output_contract,
        "deterministic_accuracy": deterministic_accuracy,
        "final_answer_judge": final_answer_judge,
        "case_pass": case_pass,
        "judge_reason": judge_result["reason"],
        "grader_versions": {
            "deterministic": "1",
            "final_answer_judge": judge_result.get("grader_version", "1"),
            "judge_model": judge_result.get("model", judge_model),
            "judge_prompt_sha256": judge_result.get("prompt_sha256"),
        },
        "diagnostics": {
            "trace_complete": bool(trace_manifest.get("complete")),
            "missing_trace_evidence": trace_manifest.get("missing") or [],
        },
        "graded_at": utc_now(),
    }
    write_json(grades_root / "output-contract.json", {
        "run_id": trial["run_id"],
        "trial_id": trial["trial_id"],
        "bundle_digest": trial["artifact_bundle_digest"],
        "pass": output_contract,
        "checks": deterministic["contract_checks"],
    })
    write_json(grades_root / "deterministic-accuracy.json", {
        "run_id": trial["run_id"],
        "trial_id": trial["trial_id"],
        "bundle_digest": trial["artifact_bundle_digest"],
        "pass": deterministic_accuracy,
        "checks": deterministic["accuracy_checks"],
    })
    write_json(grades_root / "final-answer-judge.json", {
        **judge_result,
        "run_id": trial["run_id"],
        "trial_id": trial["trial_id"],
        "bundle_digest": trial["artifact_bundle_digest"],
    })
    write_json(grades_root / "summary.json", summary)
    render_reports(trial_root, summary)

    trial["status"] = "graded"
    trial["graded_at"] = summary["graded_at"]
    trial["grade_summary"] = str(grades_root / "summary.json")
    write_json(trial_root / "trial.json", trial)
    manifest["status"] = "graded"
    manifest["graded_at"] = summary["graded_at"]
    manifest["grader"] = {
        "repository": "ai-analyst-course-evals",
        "repository_commit": _git_commit(REPO_ROOT),
        "reference_version": str(reference["case_version"]),
        "judge_model": judge_model,
    }
    write_json(manifest_path, manifest)
    with (run_root / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "at": summary["graded_at"],
            "event": "trial_graded",
            "trial_id": trial["trial_id"],
            "bundle_digest": trial["artifact_bundle_digest"],
            "case_pass": case_pass,
        }, sort_keys=True) + "\n")
    return summary


def _git_commit(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None

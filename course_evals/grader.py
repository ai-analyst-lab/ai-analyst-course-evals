"""Verify and grade a locked full-analysis run without changing its submission."""

from __future__ import annotations

import hashlib
import html
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from .graders.deterministic.artifact_contract import grade_artifact_contract
from .graders.deterministic.cross_artifact import csv_result, grade_cross_table, json_table_result
from .graders.deterministic.sql.compare_v1 import compare_results
from .graders.deterministic.sql.diagnostics_v1 import diagnose_sql
from .graders.deterministic.sql.execute_v1 import SnowflakeExecutor
from .graders.deterministic.sql.safety_v1 import inspect_sql
from .runners.model import run_model_judge


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
    trace_root = trial_root / "trace"
    trace_manifest_path = trace_root / "manifest.json"
    if not trace_manifest_path.is_file():
        raise ValueError("locked trial is missing its trace manifest")
    trace_manifest = read_json(trace_manifest_path)
    trace_observed = []
    for record in trace_manifest.get("files") or []:
        path = trace_root / record["path"]
        if not path.is_file():
            raise ValueError(f"locked trace artifact is missing: {record['path']}")
        actual = {"path": record["path"], "sha256": digest_file(path), "bytes": path.stat().st_size}
        if actual != record:
            raise ValueError(f"locked trace artifact changed: {record['path']}")
        trace_observed.append(actual)
    trace_digest = digest_payload(trace_observed)
    if trace_digest != trace_manifest.get("bundle_digest"):
        raise ValueError("trace manifest bundle digest is invalid")
    if trace_digest != trial.get("trace_bundle_digest"):
        raise ValueError("trial trace digest does not match the trace manifest")
    return trial, submission


def load_case(case_id: str, case_version: str) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    case_root = REPO_ROOT / "cases" / case_id
    reference_path = case_root / "reference.yaml"
    if not reference_path.is_file():
        raise ValueError(f"course reference is missing for {case_id}")
    reference = yaml.safe_load(reference_path.read_text(encoding="utf-8")) or {}
    if str(reference.get("case_version")) != str(case_version):
        raise ValueError(
            f"course reference version {reference.get('case_version')} does not match run version {case_version}"
        )
    grading_path = case_root / "grading.yaml"
    if not grading_path.is_file():
        raise ValueError(f"course grading configuration is missing for {case_id}")
    grading = yaml.safe_load(grading_path.read_text(encoding="utf-8")) or {}
    if str(grading.get("case_version")) != str(case_version):
        raise ValueError("grading configuration version does not match the run")
    return case_root, reference, grading


def _model_evidence(submission: Path, spec: dict[str, Any]) -> dict[str, Any]:
    mapping = spec.get("evidence") or {}
    evidence: dict[str, Any] = {}
    if mapping.get("result_json_field"):
        result = read_json(submission / "result.json")
        field = mapping["result_json_field"]
        evidence[field] = result.get(field)
    if mapping.get("brief"):
        evidence["brief"] = (submission / mapping["brief"]).read_text(encoding="utf-8")
    if mapping.get("files"):
        for path in mapping["files"]:
            evidence[path] = (submission / path).read_text(encoding="utf-8")
    return evidence


def run_configured_model_graders(
    *,
    submission: Path,
    reference: dict[str, Any],
    grading: dict[str, Any],
    model: str,
    override: Callable[..., dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    records = []
    for spec in grading.get("model_graders") or []:
        if override:
            judged = override(
                case_root=REPO_ROOT / "cases" / reference["case_id"],
                submission=submission,
                reference=reference,
                model=model,
            )
        else:
            grader_id = spec["id"]
            version = grader_id.rsplit(".v", 1)[-1] if ".v" in grader_id else "1"
            rubric_path = REPO_ROOT / spec["rubric"]
            criteria_field = spec["criteria_reference_field"]
            judged = run_model_judge(
                rubric_path=rubric_path,
                evidence=_model_evidence(submission, spec),
                criteria=reference[criteria_field],
                model=model,
                grader_id=grader_id,
                grader_version=version,
            )
        judged["reason"] = student_safe_text(judged["reason"])
        judged["graded_at"] = utc_now()
        judged["blocking"] = bool(spec.get("blocking", False))
        records.append(judged)
    return records


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


def _project_root(manifest: dict[str, Any], run_root: Path) -> Path:
    configured = manifest.get("project_root")
    if configured and Path(configured).is_dir():
        return Path(configured).resolve()
    for parent in run_root.parents:
        if (parent / ".env").is_file() and (parent / "helpers").is_dir():
            return parent
    raise ValueError("cannot locate the AI Analyst project root for Snowflake execution")


def _grade_query_outputs(
    *,
    submission: Path,
    case_root: Path,
    grading: dict[str, Any],
    manifest: dict[str, Any],
    run_root: Path,
    executor: Any | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    safety_grades: list[dict[str, Any]] = []
    result_grades: list[dict[str, Any]] = []
    diagnostic_grades: list[dict[str, Any]] = []
    for output in grading.get("query_outputs") or []:
        output_id = output["output_id"]
        candidate_sql = (submission / output["submission_sql"]).read_text(encoding="utf-8")
        reference_sql = (case_root / output["reference_sql"]).read_text(encoding="utf-8")
        safety = inspect_sql(
            candidate_sql,
            allowed_sources=output.get("allowed_sources") or [],
            prohibited_functions=output.get("prohibited_functions") or [],
        )
        safety_record = {
            "grader_id": "sql.safety.v1",
            "grader_version": "1",
            "output_id": output_id,
            "submission_sha256": hashlib.sha256(candidate_sql.encode()).hexdigest(),
            **safety.as_dict(),
        }
        safety_grades.append(safety_record)
        diagnostic_grades.append(
            diagnose_sql(
                candidate_sql,
                reference_sql,
                {
                    "expected_sources": output.get("allowed_sources") or [],
                    "declared": grading.get("diagnostics") or [],
                    "rules": output.get("diagnostic_rules") or {},
                },
            )
        )
        if not safety.passed:
            result_grades.append({
                "grader_id": f"sql.result.{output['comparison']['mode']}.v1",
                "grader_version": "1",
                "output_id": output_id,
                "pass": 0,
                "status": "not_run",
                "reason": "Candidate SQL failed the safety gate.",
                "mismatches": [{"code": "sql_safety", "violations": list(safety.violations)}],
            })
            continue
        active_executor = executor or SnowflakeExecutor(
            project_root=_project_root(manifest, run_root),
            timeout_seconds=int(output.get("timeout_seconds", 60)),
            max_rows=int(output.get("max_rows", 5000)),
            query_tag=f"ai_analyst_eval:{manifest.get('run_id')}:{output_id}",
        )
        try:
            actual = active_executor.execute(candidate_sql)
            expected = active_executor.execute(reference_sql)
            result = compare_results(actual, expected, output["comparison"])
            result.update({
                "output_id": output_id,
                "candidate_query_id": actual.query_id,
                "reference_query_id": expected.query_id,
                "candidate_sql_sha256": hashlib.sha256(candidate_sql.encode()).hexdigest(),
                "reference_sql_sha256": hashlib.sha256(reference_sql.encode()).hexdigest(),
                "candidate_elapsed_ms": actual.elapsed_ms,
                "reference_elapsed_ms": expected.elapsed_ms,
            })
            submitted_table = output.get("submitted_table")
            if submitted_table:
                artifact_result = compare_results(
                    actual,
                    csv_result(submission / submitted_table),
                    output["comparison"],
                )
                artifact_result.update({
                    "grader_id": "artifact.matches_executed_sql.v1",
                    "output_id": output_id,
                    "artifact": submitted_table,
                    "candidate_query_id": actual.query_id,
                })
                result_grades.append(artifact_result)
        except Exception as exc:
            result = {
                "grader_id": f"sql.result.{output['comparison']['mode']}.v1",
                "grader_version": "1",
                "output_id": output_id,
                "pass": 0,
                "status": "error",
                "reason": student_safe_text(exc),
                "mismatches": [],
            }
        result_grades.append(result)
    return safety_grades, result_grades, diagnostic_grades


def _artifact_table(submission: Path, spec: Any):
    if isinstance(spec, str):
        return csv_result(submission / spec)
    kind = spec.get("type", "csv")
    if kind == "csv":
        return csv_result(submission / spec["path"])
    if kind == "json_table":
        return json_table_result(submission / spec["path"], spec["field"])
    raise ValueError(f"unsupported artifact table type: {kind}")


def grade_run(
    *,
    run_root: str | Path,
    trial_id: str | None = None,
    judge_model: str = "claude-opus-4-6",
    judge: Callable[..., dict[str, Any]] | None = None,
    sql_executor: Any | None = None,
) -> dict[str, Any]:
    run_root = Path(run_root).resolve()
    manifest_path = run_root / "manifest.json"
    manifest = read_json(manifest_path)
    trial_root = resolve_trial(run_root, trial_id)
    grades_root = trial_root / "grades"
    if grades_root.exists() and any(grades_root.iterdir()):
        raise ValueError("this trial already has grade records; create a new run instead of overwriting them")
    trial, submission = verify_lock(trial_root)
    case_root, reference, grading = load_case(trial["case_id"], trial["case_version"])
    data_fingerprint = manifest.get("data_fingerprint") or {}
    expected_data_fingerprint = reference["source"]["table_fingerprint"]["value"]
    if data_fingerprint.get("status") != "verified":
        raise ValueError("course grading requires a verified data snapshot fingerprint")
    if data_fingerprint.get("sha256") != expected_data_fingerprint:
        raise ValueError("run data fingerprint does not match the reviewed reference")
    artifact_grade = grade_artifact_contract(submission, grading["artifact_contract"])
    safety_grades, sql_grades, sql_diagnostics = _grade_query_outputs(
        submission=submission,
        case_root=case_root,
        grading=grading,
        manifest=manifest,
        run_root=run_root,
        executor=sql_executor,
    )
    cross_grades = []
    for spec in grading.get("cross_artifact_tables") or []:
        left = _artifact_table(submission, spec["left"])
        right = _artifact_table(submission, spec["right"])
        record = grade_cross_table(left, right, spec["comparison"])
        record["comparison_id"] = spec["id"]
        cross_grades.append(record)

    model_grades = run_configured_model_graders(
        submission=submission,
        reference=reference,
        grading=grading,
        model=judge_model,
        override=judge,
    )
    trace_manifest_path = trial_root / "trace" / "manifest.json"
    trace_manifest = read_json(trace_manifest_path) if trace_manifest_path.is_file() else {
        "complete": False,
        "missing": ["trace_manifest"],
    }
    output_contract = int(artifact_grade["pass"])
    sql_safety = int(all(record["passed"] for record in safety_grades))
    sql_result = int(bool(sql_grades) and all(record["pass"] for record in sql_grades))
    cross_artifact = int(all(record["pass"] for record in cross_grades))
    deterministic_accuracy = int(sql_safety and sql_result and cross_artifact)
    blocking_model_grades = [record for record in model_grades if record["blocking"]]
    final_answer_judge = int(bool(blocking_model_grades) and all(record["pass"] for record in blocking_model_grades))
    case_pass = int(output_contract and deterministic_accuracy and final_answer_judge)
    diagnostic_by_id: dict[str, dict[str, Any]] = {}
    for diagnostic in sql_diagnostics:
        for check in diagnostic.get("checks") or []:
            diagnostic_by_id[check["id"]] = check
    result_json = read_json(submission / "result.json")
    validation_checks = (result_json.get("methodology") or {}).get("validation_checks") or []
    trace_names = {record["path"] for record in trace_manifest.get("files") or []}
    diagnostic_by_id["query_correctness"] = {
        "id": "query_correctness",
        "status": "pass" if sql_result else "fail",
        "evidence": [record.get("output_id") for record in sql_grades],
    }
    diagnostic_by_id["validation_checks"] = {
        "id": "validation_checks",
        "status": "pass" if validation_checks else "fail",
        "evidence": validation_checks,
    }
    linkage_present = any(name.startswith("query_log_") for name in trace_names) and (
        any(name.startswith("findings_") for name in trace_names)
        or any(name.startswith("trace_receipt_") for name in trace_names)
    )
    diagnostic_by_id["query_to_finding_linkage"] = {
        "id": "query_to_finding_linkage",
        "status": "pass" if linkage_present else "fail",
        "evidence": sorted(trace_names),
    }
    diagnostic_by_id["trace_completeness"] = {
        "id": "trace_completeness",
        "status": "pass" if trace_manifest.get("complete") else "fail",
        "missing": trace_manifest.get("missing") or [],
    }
    diagnostics_record = {
        "grader_id": "analysis.diagnostics.v1",
        "grader_version": "1",
        "checks": [
            diagnostic_by_id.get(name, {
                "id": name,
                "status": "unknown",
                "reason": "No evidence rule is configured.",
            })
            for name in grading.get("diagnostics") or []
        ],
    }
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
        "sql_safety": sql_safety,
        "sql_result": sql_result,
        "cross_artifact_consistency": cross_artifact,
        "deterministic_accuracy": deterministic_accuracy,
        "final_answer_judge": final_answer_judge,
        "case_pass": case_pass,
        "judge_reason": " ".join(record["reason"] for record in blocking_model_grades),
        "grader_versions": {
            "artifact_contract": artifact_grade.get("grader_version", "1"),
            "sql": "1",
            "final_answer_judge": ",".join(record.get("grader_version", "1") for record in blocking_model_grades),
            "judge_model": ",".join(record.get("model", judge_model) for record in blocking_model_grades),
            "judge_prompt_sha256": ",".join(
                str(record.get("prompt_sha256") or record.get("rubric_sha256") or "")
                for record in blocking_model_grades
            ),
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
        "grader_id": artifact_grade["grader_id"],
        "grader_version": artifact_grade["grader_version"],
        "checks": artifact_grade["checks"],
    })
    write_json(grades_root / "deterministic-accuracy.json", {
        "run_id": trial["run_id"],
        "trial_id": trial["trial_id"],
        "bundle_digest": trial["artifact_bundle_digest"],
        "pass": deterministic_accuracy,
        "sql_safety": sql_safety,
        "sql_result": sql_result,
        "cross_artifact_consistency": cross_artifact,
    })
    for index, record in enumerate(safety_grades, start=1):
        write_json(grades_root / f"sql-safety-{index}.json", record)
    for index, record in enumerate(sql_grades, start=1):
        write_json(grades_root / f"sql-result-{index}.json", record)
    for index, record in enumerate(cross_grades, start=1):
        write_json(grades_root / f"cross-artifact-{index}.json", record)
    write_json(grades_root / "sql-diagnostics.json", {
        **diagnostics_record,
        "sql_records": sql_diagnostics,
    })
    for index, record in enumerate(model_grades, start=1):
        safe_id = str(record.get("grader_id", f"model-{index}")).replace(".", "-")
        write_json(grades_root / f"model-judge-{safe_id}.json", {
            **record,
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

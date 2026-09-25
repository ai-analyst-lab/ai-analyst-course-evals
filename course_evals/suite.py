"""Aggregate immutable case grades into a transparent suite report."""

from __future__ import annotations

import html
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _summary_for_run(run_root: Path) -> dict[str, Any]:
    trials = sorted((run_root / "trials").glob("*/grades/summary.json"))
    if len(trials) != 1:
        raise ValueError(f"{run_root} must contain exactly one graded trial")
    return _read_json(trials[0])


def _case_slices(case_id: str) -> dict[str, str]:
    reference_path = REPO_ROOT / "cases" / case_id / "reference.yaml"
    reference = yaml.safe_load(reference_path.read_text(encoding="utf-8")) or {}
    return {str(key): str(value) for key, value in (reference.get("slices") or {}).items()}


def _rate(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    records = list(records)
    attempted = len(records)
    passed = sum(int(record["case_pass"]) for record in records)
    return {
        "attempted": attempted,
        "passed": passed,
        "failed": attempted - passed,
        "accuracy": (passed / attempted) if attempted else None,
    }


def _markdown(report: dict[str, Any]) -> str:
    overall = report["overall"]
    lines = [
        f"# Evaluation suite: {report['suite_id']}",
        "",
        f"**Case accuracy:** {overall['passed']} / {overall['attempted']} ({overall['accuracy']:.0%})",
        "",
        "| Case | Status | Result | Output | Calculation | Final answer | Domain | Complexity |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for case in report["cases"]:
        lines.append(
            f"| {case['case_id']} | {case.get('status', 'graded')} | {'Pass' if case['case_pass'] else 'Fail'} | "
            f"{'Pass' if case['output_contract'] else 'Fail'} | "
            f"{'Pass' if case['deterministic_accuracy'] else 'Fail'} | "
            f"{'Pass' if case['final_answer_judge'] else 'Fail'} | "
            f"{case['slices'].get('domain', 'unclassified')} | {case['slices'].get('complexity', 'unclassified')} |"
        )
    lines.extend(["", "## Headline gates", "", "| Gate | Passed | Attempted | Accuracy |", "|---|---:|---:|---:|"])
    for gate, metrics in report["gates"].items():
        accuracy = "n/a" if metrics["accuracy"] is None else f"{metrics['accuracy']:.0%}"
        lines.append(
            f"| {gate.replace('_', ' ')} | {metrics['passed']} | {metrics['attempted']} | {accuracy} |"
        )
    lines.extend(["", "## Slices", ""])
    for dimension, values in report["slices"].items():
        lines.append(f"### {dimension.replace('_', ' ').title()}")
        lines.append("")
        lines.append("| Slice | Passed | Attempted | Accuracy |")
        lines.append("|---|---:|---:|---:|")
        for value, metrics in values.items():
            accuracy = "n/a" if metrics["accuracy"] is None else f"{metrics['accuracy']:.0%}"
            lines.append(f"| {value} | {metrics['passed']} | {metrics['attempted']} | {accuracy} |")
        lines.append("")
    lines.append("This report describes only the included cases. It does not establish performance on unrepresented work.")
    return "\n".join(lines) + "\n"


def _html(report: dict[str, Any]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(case['case_id'])}</td>"
        f"<td>{html.escape(case.get('status', 'graded'))}</td>"
        f"<td>{'Pass' if case['case_pass'] else 'Fail'}</td>"
        f"<td>{'Pass' if case['output_contract'] else 'Fail'}</td>"
        f"<td>{'Pass' if case['deterministic_accuracy'] else 'Fail'}</td>"
        f"<td>{'Pass' if case['final_answer_judge'] else 'Fail'}</td>"
        f"<td>{html.escape(case['slices'].get('domain', 'unclassified'))}</td>"
        f"<td>{html.escape(case['slices'].get('complexity', 'unclassified'))}</td>"
        "</tr>"
        for case in report["cases"]
    )
    gate_rows = []
    for gate, metrics in report["gates"].items():
        accuracy = "n/a" if metrics["accuracy"] is None else f"{metrics['accuracy']:.0%}"
        gate_rows.append(
            "<tr>"
            f"<td>{html.escape(gate.replace('_', ' '))}</td>"
            f"<td>{metrics['passed']}</td><td>{metrics['attempted']}</td>"
            f"<td>{accuracy}</td>"
            "</tr>"
        )
    slice_rows = []
    for dimension, values in report["slices"].items():
        for value, metrics in values.items():
            accuracy = "n/a" if metrics["accuracy"] is None else f"{metrics['accuracy']:.0%}"
            slice_rows.append(
                "<tr>"
                f"<td>{html.escape(dimension.replace('_', ' '))}</td>"
                f"<td>{html.escape(value.replace('_', ' '))}</td>"
                f"<td>{metrics['passed']}</td><td>{metrics['attempted']}</td><td>{accuracy}</td>"
                "</tr>"
            )
    overall = report["overall"]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Evaluation suite</title><style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:40px;color:#1f2937}}
.card{{max-width:1100px;border:1px solid #dbe3ea;border-radius:14px;padding:28px}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:10px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top}}
.metric{{display:flex;gap:20px;align-items:baseline;padding:16px 20px;background:#f7f9fc;border-left:4px solid #0877b9}}
.metric strong{{font-size:28px}}.metric span{{font-size:22px;color:#0877b9;font-weight:700}}
.note{{background:#eef6ff;border-left:4px solid #0877b9;padding:12px}}
</style></head><body><div class="card"><h1>{html.escape(report['suite_id'])}</h1>
<h2>Complete-workflow case accuracy</h2><div class="metric"><strong>{overall['passed']} of {overall['attempted']}</strong><span>{overall['accuracy']:.0%}</span></div>
<h2>Every case</h2>
<table><thead><tr><th>Case</th><th>Status</th><th>Result</th><th>Output</th><th>Calculation</th><th>Final answer</th><th>Domain</th><th>Complexity</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Headline gates</h2>
<table><thead><tr><th>Gate</th><th>Passed</th><th>Attempted</th><th>Accuracy</th></tr></thead><tbody>{''.join(gate_rows)}</tbody></table>
<h2>Slices</h2>
<table><thead><tr><th>Dimension</th><th>Slice</th><th>Passed</th><th>Attempted</th><th>Accuracy</th></tr></thead><tbody>{''.join(slice_rows)}</tbody></table>
<p class="note">This report describes only the included complete-analysis cases. It does not establish performance on unrepresented work. Small slices are descriptive.</p>
</div></body></html>"""


def build_suite_report(
    *,
    run_roots: Iterable[str | Path],
    output_root: str | Path,
    suite_id: str,
) -> dict[str, Any]:
    cases = []
    for root in run_roots:
        summary = _summary_for_run(Path(root).resolve())
        cases.append({
            "run_id": summary["run_id"],
            "trial_id": summary["trial_id"],
            "case_id": summary["case_id"],
            "case_version": summary["case_version"],
            "case_pass": int(summary["case_pass"]),
            "output_contract": int(summary["output_contract"]),
            "deterministic_accuracy": int(summary["deterministic_accuracy"]),
            "final_answer_judge": int(summary["final_answer_judge"]),
            "status": "graded",
            "slices": _case_slices(summary["case_id"]),
        })
    return build_suite_report_from_cases(cases=cases, output_root=output_root, suite_id=suite_id)


def build_suite_report_from_cases(
    *,
    cases: list[dict[str, Any]],
    output_root: str | Path,
    suite_id: str,
) -> dict[str, Any]:
    if not cases:
        raise ValueError("a suite report requires at least one graded run")
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for case in cases:
        for dimension, value in case["slices"].items():
            grouped[dimension][value].append(case)
    report = {
        "schema_version": "1",
        "suite_id": suite_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "overall": _rate(cases),
        "gates": {
            gate: _rate([{**case, "case_pass": case[gate]} for case in cases])
            for gate in ("output_contract", "deterministic_accuracy", "final_answer_judge")
        },
        "slices": {
            dimension: {value: _rate(records) for value, records in values.items()}
            for dimension, values in grouped.items()
        },
        "cases": cases,
        "limitations": [
            "Accuracy applies only to the included cases.",
            "Small slices are descriptive and should not be treated as stable population estimates.",
            "Development-set accuracy can overstate generalization after repeated tuning.",
        ],
    }
    output = Path(output_root).resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "suite-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "suite-report.md").write_text(_markdown(report), encoding="utf-8")
    (output / "suite-report.html").write_text(_html(report), encoding="utf-8")
    return report


def grade_complete_suite_manifest(
    *,
    manifest_path: str | Path,
    judge_model: str = "claude-opus-4-6",
    parallelism: int = 4,
) -> dict[str, Any]:
    """Grade every locked child run and keep execution failures in the denominator."""
    from .grader import grade_run

    manifest_path = Path(manifest_path).resolve()
    manifest = _read_json(manifest_path)
    records = list(manifest.get("cases") or [])

    def grade_record(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str] | None]:
        case_id = str(record["case_id"])
        base = {
            "run_id": record.get("run_id"),
            "trial_id": None,
            "case_id": case_id,
            "case_version": str(record.get("case_version", "1")),
            "case_pass": 0,
            "output_contract": 0,
            "deterministic_accuracy": 0,
            "final_answer_judge": 0,
            "status": str(record.get("status", "unknown")),
            "slices": _case_slices(case_id),
        }
        run_path = record.get("run_path")
        if record.get("status") != "locked" or not run_path:
            return base, None
        run_root = Path(run_path).resolve()
        summaries = sorted((run_root / "trials").glob("*/grades/summary.json"))
        try:
            summary = _read_json(summaries[0]) if len(summaries) == 1 else grade_run(
                run_root=run_root, judge_model=judge_model
            )
            return ({
                **base,
                "trial_id": summary["trial_id"],
                "case_pass": int(summary["case_pass"]),
                "output_contract": int(summary["output_contract"]),
                "deterministic_accuracy": int(summary["deterministic_accuracy"]),
                "final_answer_judge": int(summary["final_answer_judge"]),
                "status": "graded",
            }, None)
        except Exception as exc:
            base["status"] = "grading_error"
            return base, {"case_id": case_id, "error": f"{type(exc).__name__}: {exc}"}

    cases: list[dict[str, Any]] = []
    grading_errors: list[dict[str, str]] = []
    actual_parallelism = max(1, min(int(parallelism), len(records) or 1))
    with ThreadPoolExecutor(max_workers=actual_parallelism) as pool:
        futures = [pool.submit(grade_record, record) for record in records]
        for future in as_completed(futures):
            case, error = future.result()
            cases.append(case)
            if error:
                grading_errors.append(error)
    cases.sort(key=lambda case: case["case_id"])

    output_root = manifest_path.parent / "grades"
    report = build_suite_report_from_cases(
        cases=cases,
        output_root=output_root,
        suite_id=str(manifest.get("suite_id") or manifest_path.parent.name),
    )
    manifest["grading"] = {
        "status": "complete_with_errors" if grading_errors else "complete",
        "judge_model": judge_model,
        "parallelism": actual_parallelism,
        "report_path": str(output_root / "suite-report.html"),
        "errors": grading_errors,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report

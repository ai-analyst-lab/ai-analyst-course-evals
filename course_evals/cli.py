from __future__ import annotations

import argparse
import json

from .orchestrator import grade_run
from .suite import build_suite_report, grade_complete_suite_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Grade AI Analyst course runs")
    subparsers = parser.add_subparsers(dest="command", required=True)
    grade = subparsers.add_parser("grade", help="Grade one locked run")
    grade.add_argument("--run", required=True)
    grade.add_argument("--trial-id")
    grade.add_argument("--judge-model", default="claude-opus-4-6")
    report = subparsers.add_parser("report-suite", help="Aggregate already graded runs")
    report.add_argument("--run", action="append", required=True, dest="runs")
    report.add_argument("--output", required=True)
    report.add_argument("--suite-id", default="development-suite")
    grade_suite = subparsers.add_parser(
        "grade-suite", help="Grade every locked run in a complete-analysis suite manifest"
    )
    grade_suite.add_argument("--manifest", required=True)
    grade_suite.add_argument("--judge-model", default="claude-opus-4-6")
    grade_suite.add_argument("--parallelism", type=int, default=4)
    args = parser.parse_args()
    if args.command == "grade":
        result = grade_run(
            run_root=args.run,
            trial_id=args.trial_id,
            judge_model=args.judge_model,
        )
    elif args.command == "report-suite":
        result = build_suite_report(
            run_roots=args.runs,
            output_root=args.output,
            suite_id=args.suite_id,
        )
    else:
        result = grade_complete_suite_manifest(
            manifest_path=args.manifest,
            judge_model=args.judge_model,
            parallelism=args.parallelism,
        )
    print(json.dumps(result, indent=2, sort_keys=True))

#!/usr/bin/env python3
"""Grade the deterministic parts of a locked Case 1 output bundle."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from typing import Any

import yaml
from PIL import Image


CASE_DIR = Path(__file__).resolve().parent
REFERENCE = yaml.safe_load((CASE_DIR / "reference.yaml").read_text())
REQUIRED_FILES = {
    "result.json",
    "monthly-results.csv",
    "brief.md",
    "chart.png",
    "chart-data.csv",
    "calculation.sql",
}


def close(actual: Any, expected: Any, tolerance: float) -> bool:
    try:
        return math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=tolerance)
    except (TypeError, ValueError):
        return False


def record(checks: list[dict[str, Any]], check_id: str, passed: bool, detail: str) -> None:
    checks.append({"id": check_id, "passed": bool(passed), "detail": detail})


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def grade(output_dir: Path) -> dict[str, Any]:
    contract_checks: list[dict[str, Any]] = []
    accuracy_checks: list[dict[str, Any]] = []

    existing = {path.name for path in output_dir.iterdir()} if output_dir.exists() else set()
    missing = sorted(REQUIRED_FILES - existing)
    record(contract_checks, "required_files", not missing, f"missing={missing}")
    if missing:
        return {
            "case_id": REFERENCE["case_id"],
            "output_contract": 0,
            "deterministic_accuracy": 0,
            "final_answer_judge": "not_run",
            "case_pass": 0,
            "contract_checks": contract_checks,
            "accuracy_checks": accuracy_checks,
        }

    try:
        result = json.loads((output_dir / "result.json").read_text())
        record(contract_checks, "result_json_parses", True, "valid JSON")
    except Exception as exc:
        record(contract_checks, "result_json_parses", False, str(exc))
        result = {}

    required_top = {
        "case_id",
        "period",
        "monthly_results",
        "october_to_december",
        "final_answer",
        "methodology",
        "artifacts",
    }
    record(
        contract_checks,
        "result_required_sections",
        required_top <= set(result),
        f"missing={sorted(required_top - set(result))}",
    )
    record(
        contract_checks,
        "case_id",
        result.get("case_id") == REFERENCE["case_id"],
        str(result.get("case_id")),
    )
    record(
        contract_checks,
        "period",
        result.get("period") == {"start": "2024-10-01", "end_exclusive": "2025-01-01"},
        str(result.get("period")),
    )

    csv_rows = load_csv(output_dir / "monthly-results.csv")
    chart_rows = load_csv(output_dir / "chart-data.csv")
    required_columns = {
        "month",
        "completed_order_count",
        "completed_order_value",
        "average_completed_order_value",
    }
    record(contract_checks, "monthly_csv_rows", len(csv_rows) == 3, f"rows={len(csv_rows)}")
    record(
        contract_checks,
        "monthly_csv_columns",
        bool(csv_rows) and required_columns <= set(csv_rows[0]),
        f"columns={sorted(csv_rows[0]) if csv_rows else []}",
    )
    record(contract_checks, "chart_data_matches_monthly_csv", chart_rows == csv_rows, "exact CSV row comparison")

    try:
        with Image.open(output_dir / "chart.png") as image:
            width, height = image.size
            image.verify()
        record(contract_checks, "chart_is_readable_png", width >= 400 and height >= 250, f"size={width}x{height}")
    except Exception as exc:
        record(contract_checks, "chart_is_readable_png", False, str(exc))

    brief = (output_dir / "brief.md").read_text().strip()
    record(contract_checks, "brief_is_nonempty", len(brief) >= 100, f"characters={len(brief)}")

    sql = (output_dir / "calculation.sql").read_text()
    forbidden_sql = re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|MERGE|TRUNCATE)\b", sql, re.I)
    record(contract_checks, "calculation_is_read_only", forbidden_sql is None, "DML and DDL keyword scan")

    expected_rows = REFERENCE["expected"]["monthly_results"]
    result_rows = result.get("monthly_results", [])
    record(accuracy_checks, "three_months", len(result_rows) == 3, f"rows={len(result_rows)}")
    expected_by_month = {row["month"]: row for row in expected_rows}
    result_by_month = {str(row.get("month")): row for row in result_rows if isinstance(row, dict)}
    record(
        accuracy_checks,
        "month_set",
        set(result_by_month) == set(expected_by_month),
        f"months={sorted(result_by_month)}",
    )
    tolerances = REFERENCE["tolerances"]
    for month, expected in expected_by_month.items():
        actual = result_by_month.get(month, {})
        record(
            accuracy_checks,
            f"{month}_count",
            close(actual.get("completed_order_count"), expected["completed_order_count"], tolerances["count_absolute"]),
            str(actual.get("completed_order_count")),
        )
        record(
            accuracy_checks,
            f"{month}_value",
            close(actual.get("completed_order_value"), expected["completed_order_value"], tolerances["currency_absolute"]),
            str(actual.get("completed_order_value")),
        )
        record(
            accuracy_checks,
            f"{month}_average",
            close(actual.get("average_completed_order_value"), expected["average_completed_order_value"], tolerances["average_currency_absolute"]),
            str(actual.get("average_completed_order_value")),
        )

    actual_change = result.get("october_to_december", {})
    expected_change = REFERENCE["expected"]["october_to_december"]
    for field, expected in expected_change.items():
        tolerance = (
            tolerances["count_absolute"]
            if field == "completed_order_count_absolute_change"
            else tolerances["percent_change_absolute_percentage_points"]
            if field.endswith("percent_change")
            else tolerances["currency_absolute"]
        )
        record(
            accuracy_checks,
            field,
            close(actual_change.get(field), expected, tolerance),
            str(actual_change.get(field)),
        )

    output_contract = int(all(check["passed"] for check in contract_checks))
    deterministic_accuracy = int(all(check["passed"] for check in accuracy_checks))
    return {
        "case_id": REFERENCE["case_id"],
        "output_contract": output_contract,
        "deterministic_accuracy": deterministic_accuracy,
        "final_answer_judge": "not_run",
        "case_pass": 0,
        "contract_checks": contract_checks,
        "accuracy_checks": accuracy_checks,
        "note": "The case cannot pass until the separate binary final-answer judge runs.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()
    payload = grade(args.output_dir.resolve())
    rendered = json.dumps(payload, indent=2) + "\n"
    if args.write:
        args.write.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()

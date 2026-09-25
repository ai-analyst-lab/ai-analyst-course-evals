"""Reusable output-bundle contract checks."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from PIL import Image


GRADER_ID = "artifact.contract.v1"


def _record(checks: list[dict[str, Any]], check_id: str, passed: bool, detail: Any) -> None:
    checks.append({"id": check_id, "passed": bool(passed), "detail": detail})


def grade_artifact_contract(submission: Path, config: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    existing = {path.name for path in submission.iterdir() if path.is_file()}
    required = set(config.get("required_files") or [])
    missing = sorted(required - existing)
    unexpected = sorted(existing - required) if config.get("exact_file_set", True) else []
    _record(checks, "required_files", not missing, {"missing": missing})
    _record(checks, "unexpected_files", not unexpected, {"unexpected": unexpected})

    json_config = config.get("result_json") or {}
    result: dict[str, Any] = {}
    if json_config:
        try:
            value = json.loads((submission / json_config.get("path", "result.json")).read_text())
            result = value if isinstance(value, dict) else {}
            _record(checks, "result_json_parses", isinstance(value, dict), "JSON object required")
        except Exception as exc:
            _record(checks, "result_json_parses", False, str(exc))
        required_sections = set(json_config.get("required_sections") or [])
        _record(checks, "result_required_sections", required_sections <= set(result), {"missing": sorted(required_sections - set(result))})
        if json_config.get("case_id"):
            _record(checks, "case_id", result.get("case_id") == json_config["case_id"], result.get("case_id"))

    for spec in config.get("csv", []):
        path = submission / spec["path"]
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
                columns = reader.fieldnames or []
            required_columns = spec.get("columns") or []
            _record(checks, f"{spec['id']}_columns", columns == required_columns, {"actual": columns, "expected": required_columns})
            minimum = spec.get("min_rows", 0)
            maximum = spec.get("max_rows")
            rows_ok = len(rows) >= minimum and (maximum is None or len(rows) <= maximum)
            _record(checks, f"{spec['id']}_rows", rows_ok, {"rows": len(rows), "min": minimum, "max": maximum})
        except Exception as exc:
            _record(checks, f"{spec['id']}_readable", False, str(exc))

    image_config = config.get("image")
    if image_config:
        try:
            with Image.open(submission / image_config["path"]) as image:
                width, height = image.size
                image.verify()
            passed = width >= image_config.get("min_width", 1) and height >= image_config.get("min_height", 1)
            _record(checks, "chart_is_readable", passed, {"width": width, "height": height})
        except Exception as exc:
            _record(checks, "chart_is_readable", False, str(exc))

    text_config = config.get("text")
    if text_config:
        try:
            content = (submission / text_config["path"]).read_text(encoding="utf-8").strip()
            _record(checks, "brief_length", len(content) >= text_config.get("min_characters", 1), {"characters": len(content)})
        except Exception as exc:
            _record(checks, "brief_length", False, str(exc))

    return {
        "grader_id": GRADER_ID,
        "grader_version": "1",
        "pass": int(all(check["passed"] for check in checks)),
        "status": "pass" if all(check["passed"] for check in checks) else "fail",
        "checks": checks,
    }

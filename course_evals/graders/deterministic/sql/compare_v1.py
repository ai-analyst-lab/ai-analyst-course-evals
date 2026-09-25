"""Deterministically compare normalized SQL result tables."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from decimal import Decimal
from typing import Any

from .normalize_v1 import normalize_name, normalize_value, rows_as_dicts


GRADER_VERSION = "1"


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _equal(actual: Any, expected: Any, rule: dict[str, Any]) -> bool:
    actual = normalize_value(actual, rule)
    expected = normalize_value(expected, rule)
    if actual is None or expected is None:
        return actual is None and expected is None
    if rule.get("type") in {"decimal", "number"}:
        difference = abs(Decimal(actual) - Decimal(expected))
        absolute = Decimal(str(rule.get("absolute_tolerance", 0)))
        relative = Decimal(str(rule.get("relative_tolerance", 0)))
        permitted = max(absolute, abs(Decimal(expected)) * relative)
        return difference <= permitted
    return actual == expected


def _row_signature(row: dict[str, Any], columns: dict[str, dict[str, Any]]) -> tuple[Any, ...]:
    return tuple(normalize_value(row.get(name), rule) for name, rule in columns.items())


def compare_results(actual: Any, expected: Any, config: dict[str, Any]) -> dict[str, Any]:
    mode = config.get("mode", "multiset_table")
    aliases = config.get("aliases") or {}
    actual_rows = rows_as_dicts(actual, aliases)
    expected_rows = rows_as_dicts(expected, aliases)
    actual_columns = {
        aliases.get(normalize_name(column["name"]), normalize_name(column["name"]))
        for column in actual.columns
    }
    expected_columns = {normalize_name(column["name"]) for column in expected.columns}
    required = {normalize_name(name) for name in config.get("columns", {})}
    missing_columns = sorted(required - actual_columns)
    extra_columns = sorted(actual_columns - expected_columns)
    mismatches: list[dict[str, Any]] = []

    if actual.truncated or expected.truncated:
        mismatches.append({"code": "result_too_large", "actual_truncated": actual.truncated, "expected_truncated": expected.truncated})
    if missing_columns:
        mismatches.append({"code": "missing_columns", "columns": missing_columns})
    if extra_columns and not config.get("allow_extra_columns", False):
        mismatches.append({"code": "extra_columns", "columns": extra_columns})

    columns = {normalize_name(name): rule for name, rule in config.get("columns", {}).items()}
    keys = [normalize_name(name) for name in config.get("keys", [])]

    if not missing_columns:
        if mode == "scalar":
            if len(actual_rows) != 1 or len(expected_rows) != 1:
                mismatches.append({"code": "row_count", "actual": len(actual_rows), "expected": len(expected_rows)})
            elif columns:
                name = next(iter(columns))
                if not _equal(actual_rows[0].get(name), expected_rows[0].get(name), columns[name]):
                    mismatches.append({"code": "value", "column": name, "actual": actual_rows[0].get(name), "expected": expected_rows[0].get(name)})
        elif mode == "keyed_table":
            actual_key_counts = Counter(tuple(row.get(key) for key in keys) for row in actual_rows)
            expected_key_counts = Counter(tuple(row.get(key) for key in keys) for row in expected_rows)
            duplicate_actual = sorted((key, count) for key, count in actual_key_counts.items() if count > 1)
            duplicate_expected = sorted((key, count) for key, count in expected_key_counts.items() if count > 1)
            if duplicate_actual:
                mismatches.append({"code": "duplicate_keys", "side": "actual", "keys": duplicate_actual})
            if duplicate_expected:
                mismatches.append({"code": "duplicate_keys", "side": "expected", "keys": duplicate_expected})
            actual_by_key = {tuple(row.get(key) for key in keys): row for row in actual_rows}
            expected_by_key = {tuple(row.get(key) for key in keys): row for row in expected_rows}
            missing_keys = sorted(set(expected_by_key) - set(actual_by_key), key=str)
            extra_keys = sorted(set(actual_by_key) - set(expected_by_key), key=str)
            if missing_keys:
                mismatches.append({"code": "missing_rows", "keys": missing_keys})
            if extra_keys:
                mismatches.append({"code": "extra_rows", "keys": extra_keys})
            for key in sorted(set(actual_by_key) & set(expected_by_key), key=str):
                for name, rule in columns.items():
                    if not _equal(actual_by_key[key].get(name), expected_by_key[key].get(name), rule):
                        mismatches.append({"code": "value", "key": key, "column": name, "actual": actual_by_key[key].get(name), "expected": expected_by_key[key].get(name)})
        elif mode in {"multiset_table", "ordered_table"}:
            actual_signatures = [_row_signature(row, columns) for row in actual_rows]
            expected_signatures = [_row_signature(row, columns) for row in expected_rows]
            if mode == "ordered_table":
                if actual_signatures != expected_signatures:
                    mismatches.append({"code": "ordered_rows_differ", "actual": actual_signatures[:20], "expected": expected_signatures[:20]})
            else:
                actual_counter = Counter(actual_signatures)
                expected_counter = Counter(expected_signatures)
                if actual_counter != expected_counter:
                    missing = list((expected_counter - actual_counter).elements())
                    extra = list((actual_counter - expected_counter).elements())
                    mismatches.append({"code": "row_multiset", "missing": missing[:20], "extra": extra[:20]})
        else:
            mismatches.append({"code": "unsupported_comparison_mode", "mode": mode})

    result = {
        "grader_id": f"sql.result.{mode}.v1",
        "grader_version": GRADER_VERSION,
        "pass": int(not mismatches),
        "status": "pass" if not mismatches else "fail",
        "mode": mode,
        "actual_row_count": len(actual_rows),
        "expected_row_count": len(expected_rows),
        "actual_result_sha256": _digest(actual_rows),
        "expected_result_sha256": _digest(expected_rows),
        "normalization_sha256": _digest(config),
        "mismatches": mismatches,
    }
    return result

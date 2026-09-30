"""Strict result comparison. V1 remains available for historical case definitions.

Keys use the same normalization as values. Unordered approximate comparisons
require explicit keys; we never silently ignore a numeric tolerance.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _name(value):
    return str(value).strip().lower()


def normalize(value, rule):
    if value is None:
        return None
    kind = rule.get("type", "string")
    if kind in {"number", "decimal", "integer"}:
        if isinstance(value, bool):
            raise ValueError("boolean is not a numeric result")
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError("non-finite numeric result")
        if kind == "integer":
            if number != number.to_integral_value():
                raise ValueError("fractional value in integer column")
            return int(number)
        return number
    if kind == "boolean":
        text = str(value).strip().lower()
        if text not in {"true", "false", "0", "1"}:
            raise ValueError("unrecognized boolean")
        return text in {"true", "1"}
    if kind == "date":
        # A datetime is not silently truncated: case authors must specify that rule.
        if isinstance(value, datetime):
            raise ValueError("timestamp supplied for date column")
        return date.fromisoformat(str(value)).isoformat()
    if kind == "timestamp":
        value = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if value.tzinfo is None:
            if rule.get("naive_timezone") != "UTC":
                raise ValueError("timezone missing; declare naive_timezone: UTC or supply timezone")
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if kind != "string":
        raise ValueError(f"unknown comparison type: {kind}")
    return str(value)


def _equal(a, b, rule):
    if a is None or b is None:
        return a is None and b is None
    if rule.get("type") in {"decimal", "number"}:
        absolute = Decimal(str(rule.get("absolute_tolerance", 0)))
        relative = Decimal(str(rule.get("relative_tolerance", 0)))
        return abs(a - b) <= max(absolute, abs(b) * relative)
    return a == b


def compare_results(actual: Any, expected: Any, config: dict) -> dict:
    mode = config.get("mode", "multiset_table")
    raw_columns = config.get("columns") or {}
    columns = {_name(k): v for k, v in raw_columns.items()}
    keys = [_name(k) for k in config.get("keys", [])]
    aliases = {_name(k): _name(v) for k, v in (config.get("aliases") or {}).items()}
    if not columns or len(columns) != len(raw_columns):
        raise ValueError("comparison requires unique, nonempty column rules")
    if mode not in {"scalar", "keyed_table", "ordered_table", "multiset_table"}:
        raise ValueError(f"unknown comparison mode: {mode}")
    if mode == "scalar" and len(columns) != 1:
        raise ValueError("scalar comparison requires exactly one column")
    if mode == "keyed_table" and (not keys or len(keys) != len(set(keys)) or not set(keys) <= set(columns)):
        raise ValueError("keyed comparison requires unique keys with column rules")
    for name, rule in columns.items():
        for field in ("absolute_tolerance", "relative_tolerance"):
            tolerance = Decimal(str(rule.get(field, 0)))
            if not tolerance.is_finite() or tolerance < 0:
                raise ValueError("tolerance must be finite and nonnegative")
            if tolerance and (mode == "multiset_table" or name in keys or rule.get("type") not in {"number", "decimal"}):
                raise ValueError("numeric tolerances require non-key values in scalar, keyed or ordered comparison")
    mismatches = []

    def rows(result, side):
        names = [aliases.get(_name(c["name"]), _name(c["name"])) for c in result.columns]
        if len(set(names)) != len(names):
            mismatches.append({"code": "duplicate_columns", "side": side})
            return None
        missing = set(columns) - set(names)
        extra = set(names) - set(columns)
        if missing or (extra and not config.get("allow_extra_columns", False)):
            mismatches.append({"code": "column_contract", "side": side, "missing": sorted(missing), "extra": sorted(extra)})
            return None
        parsed = []
        for index, row in enumerate(result.rows):
            try:
                item = dict(zip(names, row, strict=True))
                parsed.append({name: normalize(item[name], rule) for name, rule in columns.items()})
            except (ValueError, TypeError, InvalidOperation, OverflowError) as exc:
                mismatches.append({"code": "invalid_value", "side": side, "row": index, "reason": str(exc)})
                return None
        return parsed

    a, b = rows(actual, "actual"), rows(expected, "expected")
    if actual.truncated or expected.truncated:
        mismatches.append({"code": "result_too_large"})

    def compare_row(left, right, key):
        for name, rule in columns.items():
            if not _equal(left[name], right[name], rule):
                mismatches.append({"code": "value", "key": key, "column": name, "actual": left[name], "expected": right[name]})

    if a is not None and b is not None:
        if mode == "keyed_table":
            def keyed(rows, side):
                counts = Counter(tuple(row[key] for key in keys) for row in rows)
                duplicates = [(key, count) for key, count in counts.items() if count > 1]
                if duplicates:
                    mismatches.append({"code": "duplicate_keys", "side": side, "keys": duplicates})
                return {tuple(row[key] for key in keys): row for row in rows}
            ak, bk = keyed(a, "actual"), keyed(b, "expected")
            if ak.keys() != bk.keys():
                mismatches.append({"code": "row_keys", "missing": sorted(bk.keys() - ak.keys(), key=str), "extra": sorted(ak.keys() - bk.keys(), key=str)})
            for key in sorted(ak.keys() & bk.keys(), key=str):
                compare_row(ak[key], bk[key], key)
        elif mode == "multiset_table":
            ac = Counter(tuple(row.values()) for row in a)
            bc = Counter(tuple(row.values()) for row in b)
            if ac != bc:
                mismatches.append({"code": "row_multiset", "missing": list((bc - ac).elements())[:20], "extra": list((ac - bc).elements())[:20]})
        else:
            if len(a) != len(b) or (mode == "scalar" and (len(a) != 1 or len(b) != 1)):
                mismatches.append({"code": "row_count", "actual": len(a), "expected": len(b)})
            for index, (left, right) in enumerate(zip(a, b)):
                compare_row(left, right, index)
    invalid_reference = any(m.get("side") == "expected" for m in mismatches) or expected.truncated
    return {
        "grader_id": f"sql.result.{mode}.v2", "grader_version": "2", "mode": mode,
        "pass": int(not mismatches), "status": "error" if invalid_reference else ("fail" if mismatches else "pass"),
        "actual_row_count": len(actual.rows), "expected_row_count": len(expected.rows),
        "actual_result_sha256": _digest(actual.rows), "expected_result_sha256": _digest(expected.rows),
        "normalization_sha256": _digest(config), "mismatches": mismatches,
    }

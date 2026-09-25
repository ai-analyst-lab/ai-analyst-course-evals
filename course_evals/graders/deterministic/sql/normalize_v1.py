"""Normalize query results according to explicit case comparison rules."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any


def normalize_name(value: str) -> str:
    return str(value).strip().lower()


def normalize_value(value: Any, rule: dict[str, Any]) -> Any:
    if value is None:
        return None
    kind = rule.get("type", "string")
    if kind == "integer":
        return int(value)
    if kind in {"decimal", "number"}:
        return Decimal(str(value))
    if kind == "boolean":
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes"}
        return bool(value)
    if kind == "date":
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)[:10]
    if kind == "timestamp":
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc).isoformat()
    return str(value)


def rows_as_dicts(result: Any, aliases: dict[str, str] | None = None) -> list[dict[str, Any]]:
    aliases = {normalize_name(k): normalize_name(v) for k, v in (aliases or {}).items()}
    names = []
    for column in result.columns:
        observed = normalize_name(column["name"])
        names.append(aliases.get(observed, observed))
    return [dict(zip(names, row, strict=True)) for row in result.rows]

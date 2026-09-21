#!/usr/bin/env python3
"""Validate the private Case 1 reference against the course Snowflake snapshot."""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path

import snowflake.connector
import yaml
from dotenv import load_dotenv


CASE_DIR = Path(__file__).resolve().parent
REFERENCE = yaml.safe_load((CASE_DIR / "reference.yaml").read_text())


def connection_kwargs() -> dict[str, str]:
    auth = os.environ.get("SNOWFLAKE_AUTHENTICATOR", "password").lower()
    kwargs = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database": os.environ["SNOWFLAKE_DATABASE"],
        "role": os.environ["SNOWFLAKE_ROLE"],
        "schema": os.environ["SNOWFLAKE_SCHEMA"],
    }
    if auth in {"programmatic_access_token", "pat"}:
        kwargs["authenticator"] = "PROGRAMMATIC_ACCESS_TOKEN"
        kwargs["token"] = os.environ["SNOWFLAKE_TOKEN"]
    else:
        kwargs["password"] = os.environ["SNOWFLAKE_PASSWORD"]
    return kwargs


def close(actual: float, expected: float, tolerance: float) -> bool:
    return math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=tolerance)


def main() -> None:
    env_path = Path(os.environ.get("AI_ANALYST_ENV", "/Users/shanebutler/projects/ai-analyst/.env"))
    load_dotenv(env_path)

    with snowflake.connector.connect(**connection_kwargs()) as connection:
        with connection.cursor() as cursor:
            cursor.execute((CASE_DIR / "reference.sql").read_text())
            primary = cursor.fetchall()
            cursor.execute((CASE_DIR / "independent-check.sql").read_text())
            independent = cursor.fetchone()
            cursor.execute(
                """
                SELECT COUNT(*), MIN(order_date), MAX(order_date),
                       COUNT(DISTINCT order_id), ROUND(SUM(total_amount), 2)
                FROM BOOTCAMP_DB.NOVAMART.ORDERS
                """
            )
            fingerprint_parts = cursor.fetchone()

    expected_rows = REFERENCE["expected"]["monthly_results"]
    assert len(primary) == len(expected_rows) == 3
    for actual, expected in zip(primary, expected_rows, strict=True):
        assert actual[0] == expected["month"]
        assert int(actual[1]) == expected["completed_order_count"]
        assert close(actual[2], expected["completed_order_value"], 0.01)
        assert close(actual[3], expected["average_completed_order_value"], 0.01)

    independent_pairs = [
        (independent[0], primary[0][1]),
        (independent[1], primary[0][2]),
        (independent[2], primary[1][1]),
        (independent[3], primary[1][2]),
        (independent[4], primary[2][1]),
        (independent[5], primary[2][2]),
    ]
    for actual, expected in independent_pairs:
        assert close(actual, expected, 0.01)

    count_change = int(primary[2][1]) - int(primary[0][1])
    value_change = float(primary[2][2]) - float(primary[0][2])
    average_change = float(primary[2][3]) - float(primary[0][3])
    expected_change = REFERENCE["expected"]["october_to_december"]
    assert count_change == expected_change["completed_order_count_absolute_change"]
    assert close(value_change, expected_change["completed_order_value_absolute_change"], 0.01)
    assert close(average_change, expected_change["average_completed_order_value_absolute_change"], 0.01)

    fingerprint_text = "|".join(str(value) for value in fingerprint_parts)
    fingerprint = hashlib.sha256(fingerprint_text.encode()).hexdigest()
    expected_fingerprint = REFERENCE["source"]["table_fingerprint"]["value"]
    assert fingerprint == expected_fingerprint, (fingerprint, expected_fingerprint)

    print("PASS: reference query, independent query, changes, and source fingerprint match")


if __name__ == "__main__":
    main()

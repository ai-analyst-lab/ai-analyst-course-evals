#!/usr/bin/env python3
"""Reproduce Case 2 through two independent Snowflake queries."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from dotenv import load_dotenv
import snowflake.connector
import yaml


CASE_DIR = Path(__file__).resolve().parent
REFERENCE = yaml.safe_load((CASE_DIR / "reference.yaml").read_text())


def connection_kwargs() -> dict:
    sibling = CASE_DIR.parents[2] / "ai-analyst"
    load_dotenv(sibling / ".env", override=False)
    kwargs = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database": os.environ["SNOWFLAKE_DATABASE"],
        "schema": os.environ.get("SNOWFLAKE_SCHEMA", "NOVAMART"),
        "role": os.environ["SNOWFLAKE_ROLE"],
    }
    auth = os.environ.get("SNOWFLAKE_AUTHENTICATOR", "password").lower().replace("-", "_")
    if auth in {"programmatic_access_token", "pat"}:
        kwargs.update(authenticator="PROGRAMMATIC_ACCESS_TOKEN", token=os.environ["SNOWFLAKE_TOKEN"])
    else:
        kwargs["password"] = os.environ["SNOWFLAKE_PASSWORD"]
    return kwargs


def main() -> None:
    fingerprint_sql = """SELECT
      (SELECT COUNT(*) FROM BOOTCAMP_DB.NOVAMART.ORDERS),
      (SELECT MIN(order_date) FROM BOOTCAMP_DB.NOVAMART.ORDERS),
      (SELECT MAX(order_date) FROM BOOTCAMP_DB.NOVAMART.ORDERS),
      (SELECT COUNT(DISTINCT order_id) FROM BOOTCAMP_DB.NOVAMART.ORDERS),
      (SELECT ROUND(SUM(total_amount),2) FROM BOOTCAMP_DB.NOVAMART.ORDERS),
      (SELECT COUNT(*) FROM BOOTCAMP_DB.NOVAMART.ORDER_ITEMS),
      (SELECT COUNT(DISTINCT order_id) FROM BOOTCAMP_DB.NOVAMART.ORDER_ITEMS),
      (SELECT SUM(quantity) FROM BOOTCAMP_DB.NOVAMART.ORDER_ITEMS),
      (SELECT ROUND(SUM(line_total),2) FROM BOOTCAMP_DB.NOVAMART.ORDER_ITEMS),
      (SELECT COUNT(*) FROM BOOTCAMP_DB.NOVAMART.PRODUCTS),
      (SELECT ROUND(SUM(cost),2) FROM BOOTCAMP_DB.NOVAMART.PRODUCTS),
      (SELECT COUNT(*) FROM BOOTCAMP_DB.NOVAMART.PROMOTIONS),
      (SELECT MIN(start_date) FROM BOOTCAMP_DB.NOVAMART.PROMOTIONS),
      (SELECT MAX(end_date) FROM BOOTCAMP_DB.NOVAMART.PROMOTIONS)"""
    with snowflake.connector.connect(**connection_kwargs()) as connection:
        with connection.cursor() as cursor:
            cursor.execute((CASE_DIR / "reference.sql").read_text())
            reference_rows = cursor.fetchall()
            cursor.execute((CASE_DIR / "independent-check.sql").read_text())
            independent_rows = cursor.fetchall()
            cursor.execute(fingerprint_sql)
            fingerprint_values = cursor.fetchone()
    if reference_rows != independent_rows:
        raise SystemExit("FAIL: reference and independent queries differ")
    observed = hashlib.sha256("|".join(str(value) for value in fingerprint_values).encode()).hexdigest()
    expected = REFERENCE["source"]["table_fingerprint"]["value"]
    if observed != expected:
        raise SystemExit(f"FAIL: source fingerprint differs: {observed}")
    expected_rows = REFERENCE["expected"]["promotion_results"]
    if len(reference_rows) != len(expected_rows):
        raise SystemExit("FAIL: expected row count differs")
    print("PASS: reference query, independent query, expected results, and source fingerprint match")


if __name__ == "__main__":
    main()

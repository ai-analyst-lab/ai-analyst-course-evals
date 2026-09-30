"""A submitted standalone calculation has no external parameter bindings.

This is an output-contract check, not the runtime's parameterized query policy.
Call after normal SQL safety has accepted the statement's parse and structure.
"""
import sqlglot
from sqlglot import exp

GRADER_VERSION = "1"
GRADER_ID = "sql.submission.standalone.v1"


def inspect_standalone(sql: str) -> dict:
    statement = sqlglot.parse_one(sql, read="snowflake")
    unbound = [{"code": "unbound_parameter", "node": type(node).__name__,
                "sql": node.sql(dialect="snowflake")}
               for node in statement.walk()
               if isinstance(node, (exp.Placeholder, exp.Parameter))]
    return {"grader_id": GRADER_ID, "grader_version": GRADER_VERSION,
            "pass": int(not unbound), "status": "fail" if unbound else "pass",
            "mismatches": unbound,
            "reason": "Submitted calculation.sql must execute without external bindings; candidate SQL is not rebound by the evaluator."}

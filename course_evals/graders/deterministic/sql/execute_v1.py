"""Execute evaluation SQL through a least-privileged Snowflake session."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from dotenv import load_dotenv
import snowflake.connector


GRADER_ID = "sql.execution.v1"


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[dict[str, Any], ...]
    rows: tuple[tuple[Any, ...], ...]
    query_id: str | None
    elapsed_ms: int
    truncated: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "columns": list(self.columns),
            "rows": [list(row) for row in self.rows],
            "query_id": self.query_id,
            "elapsed_ms": self.elapsed_ms,
            "truncated": self.truncated,
            "row_count": len(self.rows),
        }


class SnowflakeExecutor:
    def __init__(
        self,
        *,
        project_root: Path,
        timeout_seconds: int = 60,
        max_rows: int = 5000,
        query_tag: str = "ai_analyst_course_eval",
    ) -> None:
        self.project_root = project_root
        self.timeout_seconds = timeout_seconds
        self.max_rows = max_rows
        self.query_tag = query_tag
        load_dotenv(project_root / ".env", override=False)

    def _kwargs(self) -> dict[str, Any]:
        required = (
            "SNOWFLAKE_ACCOUNT",
            "SNOWFLAKE_USER",
            "SNOWFLAKE_WAREHOUSE",
            "SNOWFLAKE_DATABASE",
            "SNOWFLAKE_ROLE",
        )
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            raise ValueError(f"Snowflake evaluation is missing environment variables: {missing}")
        kwargs: dict[str, Any] = {
            "account": os.environ["SNOWFLAKE_ACCOUNT"],
            "user": os.environ["SNOWFLAKE_USER"],
            "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
            "database": os.environ["SNOWFLAKE_DATABASE"],
            "role": os.environ["SNOWFLAKE_ROLE"],
            "schema": os.environ.get("SNOWFLAKE_SCHEMA", "NOVAMART"),
            "session_parameters": {
                "QUERY_TAG": self.query_tag,
                "STATEMENT_TIMEOUT_IN_SECONDS": self.timeout_seconds,
            },
        }
        auth = os.environ.get("SNOWFLAKE_AUTHENTICATOR", "password").lower().replace("-", "_")
        if auth in {"programmatic_access_token", "pat"}:
            kwargs["authenticator"] = "PROGRAMMATIC_ACCESS_TOKEN"
            kwargs["token"] = os.environ.get("SNOWFLAKE_TOKEN")
        else:
            kwargs["password"] = os.environ.get("SNOWFLAKE_PASSWORD")
        if not kwargs.get("token") and not kwargs.get("password"):
            raise ValueError("Snowflake evaluation is missing its authentication credential")
        return kwargs

    def execute(self, sql: str) -> QueryResult:
        started = perf_counter()
        with snowflake.connector.connect(**self._kwargs()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchmany(self.max_rows + 1)
                query_id = getattr(cursor, "sfqid", None)
                description = cursor.description or []
        truncated = len(rows) > self.max_rows
        kept = rows[: self.max_rows]
        columns = tuple(
            {
                "name": str(item[0]),
                "type_code": str(item[1]),
            }
            for item in description
        )
        return QueryResult(
            columns=columns,
            rows=tuple(tuple(row) for row in kept),
            query_id=query_id,
            elapsed_ms=round((perf_counter() - started) * 1000),
            truncated=truncated,
        )

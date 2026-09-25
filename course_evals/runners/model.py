"""Run a versioned narrow model judge with structured JSON output."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def run_model_judge(
    *,
    rubric_path: Path,
    evidence: dict[str, Any],
    criteria: dict[str, Any],
    model: str,
    grader_id: str,
    grader_version: str,
) -> dict[str, Any]:
    rubric = rubric_path.read_text(encoding="utf-8")
    prompt = (
        rubric
        + "\n\nEVIDENCE\n"
        + json.dumps(evidence, indent=2, sort_keys=True)
        + "\n\nREVIEWED CRITERIA\n"
        + json.dumps(criteria, indent=2, sort_keys=True)
    )
    output_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["pass", "reason", "labels"],
        "properties": {
            "pass": {"type": "integer", "enum": [0, 1]},
            "reason": {"type": "string"},
            "labels": {"type": "array", "items": {"type": "string"}},
        },
    }
    with tempfile.TemporaryDirectory(prefix="course-eval-judge-") as temporary:
        completed = subprocess.run(
            [
                "claude",
                "--print",
                "--model",
                model,
                "--no-session-persistence",
                "--output-format",
                "json",
                "--json-schema",
                json.dumps(output_schema, separators=(",", ":")),
                "--strict-mcp-config",
                "--mcp-config",
                '{"mcpServers":{}}',
                "--permission-mode",
                "dontAsk",
                "--permission-prompts",
                "none",
                "--tools=",
                "--allowedTools=",
                prompt,
            ],
            cwd=temporary,
            text=True,
            capture_output=True,
            check=False,
            timeout=180,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"model judge failed: {completed.stderr.strip()}")
        outer = json.loads(completed.stdout)
        result = outer.get("structured_output") if isinstance(outer, dict) else None
    if not isinstance(result, dict) or "pass" not in result or "reason" not in result:
        raise ValueError("model judge must return pass and reason")
    return {
        "grader_id": grader_id,
        "grader_version": grader_version,
        "model": model,
        "rubric_sha256": hashlib.sha256(rubric.encode()).hexdigest(),
        "evidence_sha256": hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest(),
        "criteria_sha256": hashlib.sha256(json.dumps(criteria, sort_keys=True).encode()).hexdigest(),
        "pass": int(bool(result["pass"])),
        "reason": str(result["reason"]),
        "labels": result.get("labels") or [],
    }

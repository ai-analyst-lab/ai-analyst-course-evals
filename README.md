# AI Analyst course evaluations

This repository stores course development references, reviewed reference queries, human labels, and grader configuration for AI Analyst evaluations.

Do not clone it into the AI Analyst repository or expose it before the first blind run is locked. After release, it becomes the shared development evaluation set. A sibling checkout on the same accessible filesystem is not a security boundary for a code-enabled evaluation process.

Public tasks, output schemas, and run management belong in `ai-analyst`. References are applied only after an evaluated output has been locked.

## Grade a locked run

From this repository:

```bash
python3 -m course_evals grade --run ../ai-analyst/working/evals/runs/<run-id>
```

The grader verifies the artifact hashes, runs deterministic checks, runs the binary final-answer judge, and writes student-safe grades and reports back to that run. It never edits the locked submission.

## Development versus held out

The first course run should be completed and locked before students receive this repository. After release, these references are intentionally visible so students can diagnose failures and improve their systems.

Do not describe later runs of these cases as held out. A company-grade held-out set should remain in a separate repository or service that the evaluated system cannot access. It should be used only to test whether improvements generalize beyond the development cases.

## Current cases

- `novamart-monthly-operating-review-001`: first end-to-end Session 6 analysis case

## Validate Case 1

With the course Snowflake credentials available through the AI Analyst `.env` file:

```bash
python3 cases/novamart-monthly-operating-review-001/validate_reference.py
```

Grade the deterministic parts of an output bundle:

```bash
python3 cases/novamart-monthly-operating-review-001/grade_submission.py path/to/output
```

The deterministic grader intentionally leaves the final-answer judge as `not_run`. A case cannot receive a passing headline grade until the separate binary judge runs.

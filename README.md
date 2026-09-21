# AI Analyst private evaluation references

This repository stores private reference answers, reviewed reference queries, human labels, and private grader configuration for AI Analyst evaluations.

It must not be cloned into a student workspace or exposed to the system being evaluated. A sibling checkout on the same accessible filesystem is not a security boundary for a code-enabled evaluation process.

Public tasks, output schemas, and runner code belong in `ai-analyst`. Private references are applied only after an evaluated output has been locked.

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

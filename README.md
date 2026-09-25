# AI Analyst course evaluations

This repository stores course development references, reviewed reference queries, human labels, and grader configuration for AI Analyst evaluations.

Clone this repository beside—not inside—the AI Analyst repository, and only after the first blind run is locked. Once it is available locally, it becomes the shared development evaluation set. A sibling checkout on the same accessible filesystem is not a security boundary for a code-enabled evaluation process.

Public tasks, output schemas, and run management belong in `ai-analyst`. References are applied only after an evaluated output has been locked.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
```

Use `.venv/bin/python` for the commands below so the SQL parser, Snowflake connector, and report dependencies are available.

## Grade a locked run

From this repository:

```bash
.venv/bin/python -m course_evals grade --run ../ai-analyst/working/evals/runs/<run-id>
```

The grader verifies the artifact hashes, runs deterministic checks, runs the binary final-answer judge, and writes student-safe grades and reports back to that run. It never edits the locked submission.

## Development versus held out

The first course run should be completed and locked before students receive this repository. After release, these references are intentionally visible so students can diagnose failures and improve their systems.

Do not describe later runs of these cases as held out. A company-grade held-out set should remain in a separate repository or service that the evaluated system cannot access. It should be used only to test whether improvements generalize beyond the development cases.

## Current cases

The primary Session 6 development set contains 20 complete-analysis cases. Their public tasks live in the sibling AI Analyst repository under `evals/cases/public/`. This repository contains one reviewed reference package per case under `cases/`.

`novamart-support-sla-breach-002` is the live harder case. Its public task does not reveal NovaMart's severity-specific SLA definition. The evaluated output is still graded normally. Missing context is not a separate failure gate.

The focused SQL suite remains available under `focused-cases/` as an optional component-level development tool. It is not the primary Session 6 system-accuracy set.

Use `SESSION-6-REFERENCE-REVIEW.md` for the human review required before these reference packages are approved for delivery.

Each case contains a reviewed reference, grader configuration, and independent reference check. The reusable grader implementations live under `course_evals/graders/`. Cases configure those graders instead of copying evaluator code into each case directory.

## Validate the references

With the course Snowflake credentials available through the AI Analyst `.env` file:

```bash
.venv/bin/python cases/novamart-monthly-operating-review-001/validate_reference.py
.venv/bin/python cases/novamart-promotion-profitability-002/validate_reference.py
```

## What the SQL grader does

The SQL grader does not require the submitted SQL text to match the reference SQL. It:

1. parses the submitted SQL and rejects writes, multiple statements, and sources outside the case allowlist;
2. executes the submitted SQL and the independently reviewed reference SQL against the same Snowflake snapshot;
3. normalizes declared names and types;
4. compares scalar, keyed-table, multiset-table, or ordered-table results using case-specific tolerances; and
5. separately checks that the saved result table matches what the submitted SQL actually returned.

This means a different correct query can pass. A query that returns the wrong values cannot pass just because its text resembles the reference.

## Grade the complete Session 6 suite

After the AI Analyst suite runner locks its child runs, grade the suite manifest:

```bash
.venv/bin/python -m course_evals grade-suite \
  --manifest ../ai-analyst/working/evals/suites/<suite-run-id>/manifest.json \
  --parallelism 4
```

The suite report writes JSON, Markdown, and HTML. It keeps every attempt in the denominator and reports overall case accuracy, gate accuracy, and configured domain, task, complexity, data-shape, and risk slices. It does not calculate precision, recall, or F1 because these cases are full analytical tasks, not positive and negative classifications.

## Grade the focused SQL suite

Run the public suite from AI Analyst first. Each child trial receives the public task but not this repository. Once the run is locked, grade it from the AI Analyst repository with:

```bash
python3 -m helpers.evals.cli grade-suite \
  --run-id <run-id> \
  --manifest evals/focused/public/session6-sql-development.yaml \
  --references ../ai-analyst-course-evals/focused-cases/session6-sql-development.yaml \
  --project-root . \
  --runs-root working/evals/runs
```

This produces a separate focused-calculation scorecard. Do not combine it with complete-analysis accuracy.

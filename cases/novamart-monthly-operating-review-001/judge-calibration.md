# Final-answer judge calibration

Date: September 21, 2026

Model: `claude-opus-4-6`

The judge received only the `final_answer` object, reviewed answer criteria, prohibited claims, and the judge instruction. It did not receive SQL, trace files, grader results, or private reasoning.

## Results

| Fixture | Expected | Observed | Result |
|---|---:|---:|---|
| Reviewed golden answer | 1 | 1 | Pass |
| Wrong primary contributor | 0 | 0 | Pass |
| Correct contributor with unsupported causal recommendation | 0 | 0 | Pass |

## What this establishes

The first judge draft distinguishes the reviewed answer from two important failure modes:

- a materially wrong analytical conclusion; and
- a plausible descriptive conclusion followed by an unsupported causal action.

## What this does not establish

Three fixtures are not enough to trust the judge at scale. Before release, add semantic paraphrases, partial answers, subtle contradictions, recommendation-only failures, and human labels. Then calculate judge accuracy and inspect false passes and false failures.

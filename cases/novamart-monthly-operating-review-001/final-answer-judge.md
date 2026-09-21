# Final-answer judge contract

## Information given to the judge

The judge receives only:

- the student `final_answer` object;
- the reviewed required conclusion;
- the reviewed required recommendation;
- the reviewed prohibited claims; and
- this grading instruction.

It does not receive private chain-of-thought, the student trace, the student SQL, or grader results. Those are evaluated separately.

## Instruction

Return `1` only when all of the following are true:

1. The answer says completed-order value increased from October to December 2024.
2. The answer identifies completed-order count as the primary positive contributor.
3. The answer says lower average completed-order value offset part of that positive contribution.
4. The recommended next investigation follows the completed-order count increase and asks what drove it or whether it is sustainable.
5. The answer keeps the lower average completed-order value visible as an offset or secondary investigation.
6. The answer does not call `total_amount` revenue.
7. The answer does not claim this descriptive analysis proves causation.
8. The answer contains no material contradiction of the reviewed facts.

Otherwise return `0`.

Semantic equivalents are acceptable. Do not require exact wording.

## Output

Return JSON only:

```json
{
  "pass": 1,
  "reason": "One concise sentence tied to the criteria above."
}
```


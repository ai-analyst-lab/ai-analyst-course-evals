# Session 6 reference review

The 20 case packages are computationally verified but are not approved solely because their SQL ran. A knowledgeable reviewer should approve the analytical task, answer, and grader before delivery.

## Review each case in this order

1. Read the public `case.yaml` without opening the answer.
2. Confirm the user, decision, population, date boundary, required output, and prohibited claims are clear and realistic.
3. Review `reference.sql` independently. Confirm its source, unit of analysis, filters, joins, date logic, null handling, aggregation, and calculation.
4. Compare the rows in `reference.yaml` with the executed reference result.
5. Confirm the tolerance in `grading.yaml` is tight enough to catch a real error and loose enough to permit harmless formatting differences.
6. Confirm the accepted conclusion follows from the reviewed rows.
7. Confirm the recommended next step is useful but does not claim causation unsupported by the case.
8. Confirm the domain, task type, complexity, data shape, and primary risk labels describe the case.
9. Record reviewer, date, decision, and any required change.

## Cases

- `novamart-monthly-operating-review-001`
- `novamart-support-sla-breach-002`
- `novamart-support-resolution-003`
- `novamart-nps-segment-004`
- `novamart-session-conversion-device-005`
- `novamart-plus-order-value-006`
- `novamart-repeat-purchase-channel-007`
- `novamart-support-category-008`
- `novamart-search-session-009`
- `novamart-promotion-returns-010`
- `novamart-category-profit-011`
- `novamart-acquisition-performance-012`
- `novamart-app-version-support-013`
- `novamart-weekend-orders-014`
- `novamart-new-repeat-purchasers-015`
- `novamart-membership-cancellation-016`
- `novamart-checkout-experiment-017`
- `novamart-cancellation-device-018`
- `novamart-device-funnel-019`
- `novamart-holiday-order-mix-020`

## Approval record

For each case, add a `review` block to `reference.yaml` only after completing the review:

```yaml
review:
  status: approved
  reviewer: <name>
  reviewed_at: YYYY-MM-DD
  notes: <what was checked or changed>
```

Do not replace the existing computational review status until the human review is complete.

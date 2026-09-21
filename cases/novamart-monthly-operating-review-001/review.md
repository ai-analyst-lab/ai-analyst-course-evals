# Case 1 reference review

## Decision

The case can support a binary final-answer grade if the public task asks which factor contributed most to the October-to-December change in completed-order value and asks for the next investigation that follows that primary contributor.

## Verified results

| Month | Completed orders | Completed-order value | Average completed-order value |
|---|---:|---:|---:|
| October 2024 | 4,672 | $381,765.78 | $81.71 |
| November 2024 | 6,048 | $441,001.93 | $72.92 |
| December 2024 | 6,215 | $453,073.37 | $72.90 |

From October to December:

- completed-order count increased by 1,543, or 33.03%;
- completed-order value increased by $71,307.59, or 18.68%; and
- average completed-order value decreased by $8.81, or 10.79%.

A symmetric two-factor decomposition of `completed-order value = order count × average completed-order value` attributes approximately:

- positive $119,284.35 to the count change; and
- negative $47,976.76 to the average-value change.

These reconcile to the $71,307.59 net increase.

## Supported conclusion

Completed-order value increased because the larger completed-order count more than offset the decline in average completed-order value.

## Supported recommendation

The first follow-up should investigate what drove the completed-order count increase and whether it is sustainable. The lower average completed-order value should remain visible as an offset and secondary investigation.

## Limits

- This is descriptive analysis and does not establish why either metric changed.
- `order_date` is treated as the governing date because the public case defines it that way.
- `total_amount` is labeled completed-order value, not revenue.
- The current reference has one independent computational review but still requires a second human review before release as trusted course evaluation material.

## Data checks completed

- `ORDERS` has 47,199 rows and no duplicate `order_id` values.
- `order_date`, `order_id`, and `total_amount` contain no nulls.
- The requested quarter contains 19,838 orders, including 16,935 completed orders.
- The primary grouped query and an independent conditional-aggregation query returned identical monthly counts and values.
- Monthly results reconcile to 16,935 completed orders and $1,275,841.08 in completed-order value for the quarter.

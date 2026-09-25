# Case 2 reference review

The reference query calculates item-level merchandise economics for completed orders attached to the two named promotion IDs. It does not sum order-level values after the item join.

The independent query first aggregates economics to one row per order and then rolls orders up to promotions. It reproduces the reference values while taking a different path through the data.

The case deliberately creates two correct rankings: Holiday Sale has greater total merchandise gross profit, while Black Friday has greater merchandise gross profit per promotion day. A correct recommendation must preserve that distinction and must not claim incremental or causal impact.

The computational reference has been independently reproduced through a second SQL formulation. A second human must still review the business definition, expected results, tolerances, and accepted final answer before the case is promoted for live use.

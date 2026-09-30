WITH eligible_orders AS (
    SELECT o.order_id, o.promo_id
    FROM BOOTCAMP_DB.NOVAMART.ORDERS AS o
    WHERE o.status = 'completed'
      AND o.promo_id IN (3, 4)
),
order_economics AS (
    SELECT
        eo.order_id,
        eo.promo_id,
        SUM(oi.line_total) AS discounted_merchandise_value,
        SUM(oi.quantity * pr.cost) AS merchandise_cost
    FROM eligible_orders AS eo
    JOIN BOOTCAMP_DB.NOVAMART.ORDER_ITEMS AS oi
      ON eo.order_id = oi.order_id
    JOIN BOOTCAMP_DB.NOVAMART.PRODUCTS AS pr
      ON oi.product_id = pr.product_id
    GROUP BY eo.order_id, eo.promo_id
)
SELECT
    p.promo_name,
    p.start_date,
    p.end_date,
    DATEDIFF(day, p.start_date, p.end_date) + 1 AS promo_days,
    COUNT(*) AS completed_order_count,
    ROUND(SUM(oe.discounted_merchandise_value), 2) AS discounted_merchandise_value,
    ROUND(SUM(oe.merchandise_cost), 2) AS merchandise_cost,
    ROUND(SUM(oe.discounted_merchandise_value - oe.merchandise_cost), 2) AS merchandise_gross_profit,
    ROUND(
        SUM(oe.discounted_merchandise_value - oe.merchandise_cost)
        / (DATEDIFF(day, p.start_date, p.end_date) + 1),
        2
    ) AS gross_profit_per_day
FROM order_economics AS oe
JOIN BOOTCAMP_DB.NOVAMART.PROMOTIONS AS p
  ON oe.promo_id = p.promo_id
GROUP BY p.promo_name, p.start_date, p.end_date
ORDER BY p.start_date;

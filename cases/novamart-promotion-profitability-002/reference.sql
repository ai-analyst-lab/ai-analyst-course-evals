SELECT
    p.promo_name,
    p.start_date,
    p.end_date,
    DATEDIFF(day, p.start_date, p.end_date) + 1 AS promo_days,
    COUNT(DISTINCT o.order_id) AS completed_order_count,
    ROUND(SUM(oi.line_total), 2) AS discounted_merchandise_value,
    ROUND(SUM(oi.quantity * pr.cost), 2) AS merchandise_cost,
    ROUND(SUM(oi.line_total - oi.quantity * pr.cost), 2) AS merchandise_gross_profit,
    ROUND(
        SUM(oi.line_total - oi.quantity * pr.cost)
        / (DATEDIFF(day, p.start_date, p.end_date) + 1),
        2
    ) AS gross_profit_per_day
FROM BOOTCAMP_DB.NOVAMART.ORDERS AS o
JOIN BOOTCAMP_DB.NOVAMART.PROMOTIONS AS p
  ON o.promo_id = p.promo_id
JOIN BOOTCAMP_DB.NOVAMART.ORDER_ITEMS AS oi
  ON o.order_id = oi.order_id
JOIN BOOTCAMP_DB.NOVAMART.PRODUCTS AS pr
  ON oi.product_id = pr.product_id
WHERE o.status = 'completed'
  AND p.promo_name IN ('Black Friday', 'Holiday Sale')
GROUP BY p.promo_name, p.start_date, p.end_date
ORDER BY p.start_date;

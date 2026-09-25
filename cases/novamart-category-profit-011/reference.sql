SELECT p.category, SUM(oi.quantity) AS units,
       ROUND(SUM(oi.line_total), 2) AS merchandise_value,
       ROUND(SUM(oi.quantity * p.cost), 2) AS merchandise_cost,
       ROUND(SUM(oi.line_total - oi.quantity * p.cost), 2) AS merchandise_gross_profit,
       ROUND(100.0 * SUM(oi.line_total - oi.quantity * p.cost) / NULLIF(SUM(oi.line_total), 0), 2) AS gross_margin_pct
FROM BOOTCAMP_DB.NOVAMART.ORDERS o
JOIN BOOTCAMP_DB.NOVAMART.ORDER_ITEMS oi ON o.order_id = oi.order_id
JOIN BOOTCAMP_DB.NOVAMART.PRODUCTS p ON oi.product_id = p.product_id
WHERE o.status = 'completed' AND o.order_date >= '2024-10-01' AND o.order_date < '2025-01-01'
GROUP BY p.category ORDER BY p.category;

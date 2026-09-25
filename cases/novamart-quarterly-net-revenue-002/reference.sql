SELECT
    TO_CHAR(DATE_TRUNC('month', order_date), 'YYYY-MM') AS month,
    ROUND(SUM(
        CASE
            WHEN status = 'completed' THEN total_amount
            WHEN status = 'returned' THEN -total_amount
            ELSE 0
        END
    ), 2) AS net_revenue
FROM BOOTCAMP_DB.NOVAMART.ORDERS
WHERE order_date >= '2024-10-01'
  AND order_date < '2025-01-01'
  AND status IN ('completed', 'returned')
GROUP BY 1
ORDER BY 1;

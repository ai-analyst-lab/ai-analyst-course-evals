SELECT TO_CHAR(DATE_TRUNC('month', order_date), 'YYYY-MM') AS month,
       ROUND(SUM(IFF(status = 'completed', total_amount, 0)), 2) AS completed_order_value,
       ROUND(SUM(IFF(status = 'returned', total_amount, 0)), 2) AS returned_order_value,
       ROUND(SUM(IFF(status = 'cancelled', total_amount, 0)), 2) AS cancelled_order_value
FROM BOOTCAMP_DB.NOVAMART.ORDERS
WHERE order_date >= '2024-10-01' AND order_date < '2025-01-01'
GROUP BY 1 ORDER BY 1;

SELECT IFF(c.is_weekend, 'weekend', 'weekday') AS day_type,
       COUNT(*) AS completed_order_count, ROUND(SUM(o.total_amount), 2) AS completed_order_value,
       ROUND(AVG(o.total_amount), 2) AS average_completed_order_value
FROM BOOTCAMP_DB.NOVAMART.ORDERS o JOIN BOOTCAMP_DB.NOVAMART.CALENDAR c ON o.order_date = c.date
WHERE o.status = 'completed' AND o.order_date >= '2024-10-01' AND o.order_date < '2025-01-01'
GROUP BY 1 ORDER BY 1;

SELECT device, COUNT(*) AS order_count, COUNT_IF(status = 'cancelled') AS cancelled_order_count,
       ROUND(100.0 * COUNT_IF(status = 'cancelled') / NULLIF(COUNT(*), 0), 2) AS cancelled_order_rate_pct
FROM BOOTCAMP_DB.NOVAMART.ORDERS
WHERE order_date >= '2024-10-01' AND order_date < '2025-01-01'
GROUP BY device ORDER BY device;

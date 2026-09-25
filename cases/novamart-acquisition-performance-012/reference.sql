SELECT u.acquisition_channel, COUNT(DISTINCT o.user_id) AS purchaser_count,
       COUNT(*) AS completed_order_count, ROUND(SUM(o.total_amount), 2) AS completed_order_value,
       ROUND(AVG(o.total_amount), 2) AS average_completed_order_value
FROM BOOTCAMP_DB.NOVAMART.ORDERS o JOIN BOOTCAMP_DB.NOVAMART.USERS u ON o.user_id = u.user_id
WHERE o.status = 'completed' AND o.order_date >= '2024-10-01' AND o.order_date < '2025-01-01'
GROUP BY u.acquisition_channel ORDER BY u.acquisition_channel;

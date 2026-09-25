SELECT IFF(is_plus_member_order, 'Plus', 'Non-Plus') AS member_group,
       COUNT(*) AS completed_order_count, ROUND(SUM(total_amount), 2) AS completed_order_value,
       ROUND(AVG(total_amount), 2) AS average_completed_order_value
FROM BOOTCAMP_DB.NOVAMART.ORDERS
WHERE status = 'completed' AND order_date >= '2024-10-01' AND order_date < '2025-01-01'
GROUP BY 1 ORDER BY 1;

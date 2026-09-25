WITH user_orders AS (
  SELECT user_id, COUNT(*) AS completed_orders
  FROM BOOTCAMP_DB.NOVAMART.ORDERS
  WHERE status = 'completed' AND order_date >= '2024-10-01' AND order_date < '2025-01-01'
  GROUP BY user_id
)
SELECT u.acquisition_channel, COUNT(*) AS purchaser_count,
       COUNT_IF(o.completed_orders >= 2) AS repeat_purchaser_count,
       ROUND(100.0 * COUNT_IF(o.completed_orders >= 2) / NULLIF(COUNT(*), 0), 2) AS repeat_purchase_rate_pct
FROM user_orders o JOIN BOOTCAMP_DB.NOVAMART.USERS u ON o.user_id = u.user_id
GROUP BY u.acquisition_channel ORDER BY u.acquisition_channel;

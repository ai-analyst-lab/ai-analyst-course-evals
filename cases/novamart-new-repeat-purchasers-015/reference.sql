WITH first_completed AS (
  SELECT user_id, MIN(order_date) AS first_completed_date
  FROM BOOTCAMP_DB.NOVAMART.ORDERS WHERE status = 'completed' GROUP BY user_id
), monthly AS (
  SELECT DATE_TRUNC('month', o.order_date)::DATE AS month, o.user_id,
         IFF(DATE_TRUNC('month', f.first_completed_date) = DATE_TRUNC('month', o.order_date), 1, 0) AS is_first_time
  FROM BOOTCAMP_DB.NOVAMART.ORDERS o JOIN first_completed f ON o.user_id = f.user_id
  WHERE o.status = 'completed' AND o.order_date >= '2024-10-01' AND o.order_date < '2025-01-01'
  GROUP BY month, o.user_id, is_first_time
)
SELECT TO_CHAR(month, 'YYYY-MM') AS month, COUNT(*) AS completed_purchasers,
       COUNT_IF(is_first_time = 1) AS first_time_purchasers,
       COUNT_IF(is_first_time = 0) AS returning_purchasers,
       ROUND(100.0 * COUNT_IF(is_first_time = 1) / NULLIF(COUNT(*), 0), 2) AS first_time_share_pct
FROM monthly GROUP BY month ORDER BY month;

WITH assigned AS (
  SELECT a.user_id, a.variant, a.first_exposure_date, e.end_date
  FROM BOOTCAMP_DB.NOVAMART.EXPERIMENT_ASSIGNMENTS a
  JOIN BOOTCAMP_DB.NOVAMART.EXPERIMENTS e ON a.experiment_id = e.experiment_id
  WHERE e.experiment_name = 'checkout_redesign'
), user_outcomes AS (
  SELECT a.variant, a.user_id,
         MAX(IFF(o.order_id IS NOT NULL, 1, 0)) AS purchased,
         COALESCE(SUM(o.total_amount), 0) AS completed_order_value
  FROM assigned a LEFT JOIN BOOTCAMP_DB.NOVAMART.ORDERS o ON a.user_id = o.user_id
   AND o.status = 'completed' AND o.order_date >= a.first_exposure_date AND o.order_date <= a.end_date
  GROUP BY a.variant, a.user_id
)
SELECT variant, COUNT(*) AS assigned_users, SUM(purchased) AS completed_purchasers,
       ROUND(100.0 * SUM(purchased) / NULLIF(COUNT(*), 0), 2) AS completed_purchaser_rate_pct,
       ROUND(SUM(completed_order_value), 2) AS completed_order_value
FROM user_outcomes GROUP BY variant ORDER BY variant;

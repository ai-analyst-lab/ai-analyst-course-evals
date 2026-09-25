WITH scoped AS (
  SELECT DATE_TRUNC('month', created_date)::DATE AS month,
         severity,
         DATEDIFF('hour', created_at, COALESCE(resolved_at, '2025-01-01'::TIMESTAMP_NTZ)) AS elapsed_hours
  FROM BOOTCAMP_DB.NOVAMART.SUPPORT_TICKETS
  WHERE created_date >= '2024-10-01' AND created_date < '2025-01-01'
), classified AS (
  SELECT month, IFF(elapsed_hours > CASE severity WHEN 'critical' THEN 12 WHEN 'high' THEN 48 WHEN 'medium' THEN 72 ELSE 120 END, 1, 0) AS breached
  FROM scoped
)
SELECT TO_CHAR(month, 'YYYY-MM') AS month, COUNT(*) AS ticket_count,
       SUM(breached) AS breached_ticket_count,
       ROUND(100.0 * SUM(breached) / NULLIF(COUNT(*), 0), 2) AS breach_rate_pct
FROM classified GROUP BY month ORDER BY month;

SELECT COALESCE(cancel_reason, 'unknown') AS cancel_reason,
       COUNT(*) AS ended_membership_count,
       ROUND(AVG(DATEDIFF('day', started_at, ended_at)), 2) AS average_tenure_days
FROM BOOTCAMP_DB.NOVAMART.MEMBERSHIPS
WHERE ended_at >= '2024-10-01' AND ended_at < '2025-01-01'
GROUP BY COALESCE(cancel_reason, 'unknown') ORDER BY cancel_reason;

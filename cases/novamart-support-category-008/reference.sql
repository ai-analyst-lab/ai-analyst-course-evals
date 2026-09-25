SELECT category, COUNT(*) AS ticket_count, COUNT_IF(resolved_at IS NOT NULL) AS resolved_ticket_count,
       ROUND(MEDIAN(IFF(resolved_at IS NOT NULL, DATEDIFF('minute', created_at, resolved_at) / 60.0, NULL)), 2) AS median_resolution_hours
FROM BOOTCAMP_DB.NOVAMART.SUPPORT_TICKETS
WHERE created_date >= '2024-10-01' AND created_date < '2025-01-01'
GROUP BY category ORDER BY category;

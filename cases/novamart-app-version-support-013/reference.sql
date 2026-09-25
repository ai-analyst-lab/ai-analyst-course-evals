SELECT COALESCE(app_version, 'unknown') AS app_version, COUNT(*) AS ticket_count,
       COUNT_IF(severity IN ('high','critical')) AS high_critical_count,
       ROUND(100.0 * COUNT_IF(severity IN ('high','critical')) / NULLIF(COUNT(*), 0), 2) AS high_critical_share_pct,
       ROUND(MEDIAN(IFF(resolved_at IS NOT NULL, DATEDIFF('minute', created_at, resolved_at) / 60.0, NULL)), 2) AS median_resolution_hours
FROM BOOTCAMP_DB.NOVAMART.SUPPORT_TICKETS
WHERE created_date >= '2024-10-01' AND created_date < '2025-01-01'
GROUP BY COALESCE(app_version, 'unknown') ORDER BY app_version;

SELECT s.device, COUNT(DISTINCT s.session_id) AS session_count,
       COUNT(DISTINCT IFF(o.order_id IS NOT NULL, s.session_id, NULL)) AS purchasing_session_count,
       ROUND(100.0 * COUNT(DISTINCT IFF(o.order_id IS NOT NULL, s.session_id, NULL)) / NULLIF(COUNT(DISTINCT s.session_id), 0), 4) AS completed_order_session_rate_pct
FROM BOOTCAMP_DB.NOVAMART.SESSIONS s
LEFT JOIN BOOTCAMP_DB.NOVAMART.ORDERS o ON s.session_id = o.session_id
 AND o.status = 'completed' AND o.order_date >= '2024-10-01' AND o.order_date < '2025-01-01'
WHERE s.session_date >= '2024-10-01' AND s.session_date < '2025-01-01'
GROUP BY s.device ORDER BY s.device;

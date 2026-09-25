WITH session_flags AS (
  SELECT s.session_id,
         IFF(MAX(IFF(e.event_type = 'search', 1, 0)) = 1, 'searched', 'did_not_search') AS search_group
  FROM BOOTCAMP_DB.NOVAMART.SESSIONS s
  LEFT JOIN BOOTCAMP_DB.NOVAMART.EVENTS e ON s.session_id = e.session_id
  WHERE s.session_date >= '2024-10-01' AND s.session_date < '2025-01-01'
  GROUP BY s.session_id
), purchasers AS (
  SELECT DISTINCT session_id FROM BOOTCAMP_DB.NOVAMART.ORDERS
  WHERE status = 'completed' AND order_date >= '2024-10-01' AND order_date < '2025-01-01'
)
SELECT f.search_group, COUNT(*) AS session_count,
       COUNT_IF(p.session_id IS NOT NULL) AS purchasing_session_count,
       ROUND(100.0 * COUNT_IF(p.session_id IS NOT NULL) / NULLIF(COUNT(*), 0), 4) AS completed_order_session_rate_pct
FROM session_flags f LEFT JOIN purchasers p ON f.session_id = p.session_id
GROUP BY f.search_group ORDER BY f.search_group;

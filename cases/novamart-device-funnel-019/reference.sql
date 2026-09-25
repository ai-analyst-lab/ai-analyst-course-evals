WITH event_flags AS (
  SELECT session_id,
         MAX(IFF(event_type = 'product_view', 1, 0)) AS has_product_view,
         MAX(IFF(event_type = 'add_to_cart', 1, 0)) AS has_add_to_cart
  FROM BOOTCAMP_DB.NOVAMART.EVENTS
  WHERE event_date >= '2024-10-01' AND event_date < '2025-01-01'
  GROUP BY session_id
), purchasers AS (
  SELECT DISTINCT session_id FROM BOOTCAMP_DB.NOVAMART.ORDERS
  WHERE status = 'completed' AND order_date >= '2024-10-01' AND order_date < '2025-01-01'
)
SELECT s.device, COUNT(DISTINCT s.session_id) AS session_count,
       COUNT(DISTINCT IFF(e.has_product_view = 1, s.session_id, NULL)) AS product_view_sessions,
       COUNT(DISTINCT IFF(e.has_add_to_cart = 1, s.session_id, NULL)) AS add_to_cart_sessions,
       COUNT(DISTINCT IFF(p.session_id IS NOT NULL, s.session_id, NULL)) AS purchasing_sessions,
       ROUND(100.0 * COUNT(DISTINCT IFF(p.session_id IS NOT NULL, s.session_id, NULL)) / NULLIF(COUNT(DISTINCT s.session_id), 0), 4) AS completed_order_session_rate_pct
FROM BOOTCAMP_DB.NOVAMART.SESSIONS s
LEFT JOIN event_flags e ON s.session_id = e.session_id
LEFT JOIN purchasers p ON s.session_id = p.session_id
WHERE s.session_date >= '2024-10-01' AND s.session_date < '2025-01-01'
GROUP BY s.device ORDER BY s.device;

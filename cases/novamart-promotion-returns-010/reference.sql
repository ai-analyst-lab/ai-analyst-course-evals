SELECT p.promo_name,
       COUNT_IF(o.status = 'completed') AS completed_order_count,
       COUNT_IF(o.status = 'returned') AS returned_order_count,
       ROUND(100.0 * COUNT_IF(o.status = 'returned') / NULLIF(COUNT_IF(o.status IN ('completed','returned')), 0), 2) AS returned_share_pct,
       ROUND(SUM(IFF(o.status = 'completed', o.total_amount, 0)), 2) AS completed_order_value,
       ROUND(SUM(IFF(o.status = 'returned', o.total_amount, 0)), 2) AS returned_order_value
FROM BOOTCAMP_DB.NOVAMART.PROMOTIONS p
JOIN BOOTCAMP_DB.NOVAMART.ORDERS o ON p.promo_id = o.promo_id
WHERE p.promo_name IN ('Black Friday','Holiday Sale') AND o.order_date BETWEEN p.start_date AND p.end_date
GROUP BY p.promo_name ORDER BY p.promo_name;

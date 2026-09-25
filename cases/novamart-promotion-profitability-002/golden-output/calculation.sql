WITH promotion_orders AS (
    SELECT
        o.order_id,
        p.promo_name,
        p.start_date,
        p.end_date,
        DATEDIFF('day', p.start_date, p.end_date) + 1 AS promo_days
    FROM BOOTCAMP_DB.NOVAMART.ORDERS AS o
    INNER JOIN BOOTCAMP_DB.NOVAMART.PROMOTIONS AS p
        ON o.promo_id = p.promo_id
    WHERE UPPER(o.status) = 'COMPLETED'
      AND UPPER(p.promo_name) IN ('BLACK FRIDAY', 'HOLIDAY SALE')
),
item_profit AS (
    SELECT
        po.promo_name,
        po.start_date,
        po.end_date,
        po.promo_days,
        po.order_id,
        oi.line_total AS discounted_merchandise_value,
        oi.quantity * pr.cost AS merchandise_cost
    FROM promotion_orders AS po
    INNER JOIN BOOTCAMP_DB.NOVAMART.ORDER_ITEMS AS oi
        ON po.order_id = oi.order_id
    INNER JOIN BOOTCAMP_DB.NOVAMART.PRODUCTS AS pr
        ON oi.product_id = pr.product_id
)
SELECT
    promo_name,
    start_date,
    end_date,
    promo_days,
    COUNT(DISTINCT order_id) AS completed_order_count,
    ROUND(SUM(discounted_merchandise_value), 2) AS discounted_merchandise_value,
    ROUND(SUM(merchandise_cost), 2) AS merchandise_cost,
    ROUND(SUM(discounted_merchandise_value - merchandise_cost), 2) AS merchandise_gross_profit,
    ROUND(SUM(discounted_merchandise_value - merchandise_cost) / promo_days, 2) AS gross_profit_per_day
FROM item_profit
GROUP BY promo_name, start_date, end_date, promo_days
ORDER BY promo_name;

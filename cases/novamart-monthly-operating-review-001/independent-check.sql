SELECT
    COUNT_IF(
        status = 'completed'
        AND order_date >= '2024-10-01'
        AND order_date < '2024-11-01'
    ) AS oct_count,
    ROUND(SUM(IFF(
        status = 'completed'
        AND order_date >= '2024-10-01'
        AND order_date < '2024-11-01',
        total_amount,
        0
    )), 2) AS oct_value,
    COUNT_IF(
        status = 'completed'
        AND order_date >= '2024-11-01'
        AND order_date < '2024-12-01'
    ) AS nov_count,
    ROUND(SUM(IFF(
        status = 'completed'
        AND order_date >= '2024-11-01'
        AND order_date < '2024-12-01',
        total_amount,
        0
    )), 2) AS nov_value,
    COUNT_IF(
        status = 'completed'
        AND order_date >= '2024-12-01'
        AND order_date < '2025-01-01'
    ) AS dec_count,
    ROUND(SUM(IFF(
        status = 'completed'
        AND order_date >= '2024-12-01'
        AND order_date < '2025-01-01',
        total_amount,
        0
    )), 2) AS dec_value
FROM BOOTCAMP_DB.NOVAMART.ORDERS;


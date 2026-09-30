SELECT TO_CHAR(o.order_date, 'YYYY-MM') AS segment, 1 AS measure FROM BOOTCAMP_DB.NOVAMART.ORDERS o WHERE o.order_date >= '2024-10-01' AND o.order_date < '2025-01-01' AND o.status='completed';

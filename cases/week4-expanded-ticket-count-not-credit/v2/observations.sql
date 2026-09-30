SELECT t.severity AS segment, 1 AS measure FROM BOOTCAMP_DB.NOVAMART.SUPPORT_TICKETS t WHERE t.created_date >= '2024-10-01' AND t.created_date < '2025-01-01';

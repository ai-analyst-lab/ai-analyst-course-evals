SELECT TO_CHAR(s.session_date, 'YYYY-MM') AS segment, 1 AS measure FROM BOOTCAMP_DB.NOVAMART.SESSIONS s WHERE s.session_date >= '2024-10-01' AND s.session_date < '2025-01-01';

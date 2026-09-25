SELECT user_segment, COUNT(*) AS response_count, ROUND(AVG(score), 2) AS average_score,
       ROUND(100.0 * (COUNT_IF(score >= 9) - COUNT_IF(score <= 6)) / NULLIF(COUNT(*), 0), 2) AS nps
FROM BOOTCAMP_DB.NOVAMART.NPS_RESPONSES
WHERE response_date >= '2024-10-01' AND response_date < '2025-01-01'
GROUP BY user_segment ORDER BY user_segment;

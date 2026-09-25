"""Build the Session 6 complete-analysis development cases.

The public case definitions are written to the sibling AI Analyst repository.
Reviewed SQL, computed reference rows, and judge criteria remain here. Run this
only from the private evaluator repository after reviewing the case catalog.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import snowflake.connector
import yaml
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ANALYST_ROOT = ROOT.parent / "ai-analyst"
SNAPSHOT_QUERY = """SELECT
  (SELECT COUNT(*) FROM BOOTCAMP_DB.NOVAMART.CALENDAR) AS calendar_count,
  (SELECT COUNT(*) FROM BOOTCAMP_DB.NOVAMART.EVENTS) AS events_count,
  (SELECT COUNT(*) FROM BOOTCAMP_DB.NOVAMART.EXPERIMENTS) AS experiments_count,
  (SELECT COUNT(*) FROM BOOTCAMP_DB.NOVAMART.EXPERIMENT_ASSIGNMENTS) AS experiment_assignments_count,
  (SELECT COUNT(*) FROM BOOTCAMP_DB.NOVAMART.MEMBERSHIPS) AS memberships_count,
  (SELECT COUNT(*) FROM BOOTCAMP_DB.NOVAMART.NPS_RESPONSES) AS nps_responses_count,
  (SELECT COUNT(*) FROM BOOTCAMP_DB.NOVAMART.ORDERS) AS orders_count,
  (SELECT COUNT(*) FROM BOOTCAMP_DB.NOVAMART.ORDER_ITEMS) AS order_items_count,
  (SELECT COUNT(*) FROM BOOTCAMP_DB.NOVAMART.PRODUCTS) AS products_count,
  (SELECT COUNT(*) FROM BOOTCAMP_DB.NOVAMART.PROMOTIONS) AS promotions_count,
  (SELECT COUNT(*) FROM BOOTCAMP_DB.NOVAMART.SESSIONS) AS sessions_count,
  (SELECT COUNT(*) FROM BOOTCAMP_DB.NOVAMART.SUPPORT_TICKETS) AS support_tickets_count,
  (SELECT COUNT(*) FROM BOOTCAMP_DB.NOVAMART.USERS) AS users_count"""
SNAPSHOT_SHA256 = "fdeb62d623a6200aa9f3d5c05408be1ffe4714d25084f5e17b8558a24c05d3a3"


@dataclass(frozen=True)
class Case:
    case_id: str
    domain: str
    task_type: str
    complexity: str
    data_shape: str
    risk: str
    audience: str
    decision: str
    task: str
    tables: tuple[str, ...]
    columns: tuple[tuple[str, str, float], ...]
    keys: tuple[str, ...]
    sql: str
    primary_label: str
    primary_metric: str
    recommendation: str
    primary_direction: str = "max"
    excluded_labels: tuple[str, ...] = ()
    prohibited_claims: tuple[str, ...] = (
        "The descriptive result proves a causal explanation.",
        "The analysis establishes a business target that was not supplied.",
    )


CASES = (
    Case(
        "novamart-support-sla-breach-002", "support", "recurring_review", "high",
        "single_table", "missing_business_definition", "NovaMart support director",
        "Identify where Q4 support service-level performance needs investigation.",
        "Prepare a monthly Q4 2024 review of NovaMart's support SLA breach rate for tickets created from October 1, 2024 inclusive through January 1, 2025 exclusive. Report ticket count, breached-ticket count, and breach rate by month. Use the reviewed company SLA definition if the system has one. If it does not, choose and clearly disclose the definition used so the result can be reviewed. Identify the month with the highest breach rate and recommend what support should investigate next. Do not claim that the descriptive comparison proves why the rate changed.",
        ("SUPPORT_TICKETS",),
        (("month", "string", 0), ("ticket_count", "integer", 0), ("breached_ticket_count", "integer", 0), ("breach_rate_pct", "decimal", 0.01)),
        ("month",),
        """WITH scoped AS (
  SELECT DATE_TRUNC('month', created_date)::DATE AS month,
         severity,
         DATEDIFF('hour', created_at, COALESCE(resolved_at, '2025-01-01'::TIMESTAMP_NTZ)) AS elapsed_hours
  FROM BOOTCAMP_DB.NOVAMART.SUPPORT_TICKETS
  WHERE created_date >= '2024-10-01' AND created_date < '2025-01-01'
), classified AS (
  SELECT month, IFF(elapsed_hours > CASE severity WHEN 'critical' THEN 12 WHEN 'high' THEN 48 WHEN 'medium' THEN 72 ELSE 120 END, 1, 0) AS breached
  FROM scoped
)
SELECT TO_CHAR(month, 'YYYY-MM') AS month, COUNT(*) AS ticket_count,
       SUM(breached) AS breached_ticket_count,
       ROUND(100.0 * SUM(breached) / NULLIF(COUNT(*), 0), 2) AS breach_rate_pct
FROM classified GROUP BY month ORDER BY month""",
        "month", "breach_rate_pct",
        "Investigate severity mix, unresolved tickets, and the ticket categories contributing to the highest breach-rate month before changing staffing or service policy.",
    ),
    Case(
        "novamart-support-resolution-003", "support", "recurring_review", "medium",
        "single_table", "missingness", "NovaMart support manager",
        "Understand whether ticket volume and resolution time changed during Q4.",
        "Prepare a monthly support operating review for tickets created from October 1, 2024 inclusive through January 1, 2025 exclusive. Report ticket count, resolved-ticket count, and median resolution hours among tickets with RESOLVED_AT present. Identify the month with the highest median resolution time and recommend what the support manager should investigate next. Keep unresolved tickets visible in the limitation.",
        ("SUPPORT_TICKETS",),
        (("month", "string", 0), ("ticket_count", "integer", 0), ("resolved_ticket_count", "integer", 0), ("median_resolution_hours", "decimal", 0.01)),
        ("month",),
        """SELECT TO_CHAR(DATE_TRUNC('month', created_date), 'YYYY-MM') AS month,
       COUNT(*) AS ticket_count, COUNT_IF(resolved_at IS NOT NULL) AS resolved_ticket_count,
       ROUND(MEDIAN(IFF(resolved_at IS NOT NULL, DATEDIFF('minute', created_at, resolved_at) / 60.0, NULL)), 2) AS median_resolution_hours
FROM BOOTCAMP_DB.NOVAMART.SUPPORT_TICKETS
WHERE created_date >= '2024-10-01' AND created_date < '2025-01-01'
GROUP BY 1 ORDER BY 1""",
        "month", "median_resolution_hours",
        "Investigate category and severity mix in the slowest month while keeping unresolved tickets separate from the resolved-ticket duration calculation.",
    ),
    Case(
        "novamart-nps-segment-004", "customer_experience", "segment_review", "medium",
        "single_table", "metric_definition", "NovaMart customer experience lead",
        "Identify which customer segment's recorded Q4 responses need investigation.",
        "Compare NovaMart Q4 2024 NPS responses by USER_SEGMENT. Report response count, average score, and standard NPS, defined as promoter percentage minus detractor percentage where promoters score 9 or 10 and detractors score 0 through 6. Identify the segment with the lowest NPS and recommend what to investigate next. Do not generalize beyond recorded respondents.",
        ("NPS_RESPONSES",),
        (("user_segment", "string", 0), ("response_count", "integer", 0), ("average_score", "decimal", 0.01), ("nps", "decimal", 0.01)),
        ("user_segment",),
        """SELECT user_segment, COUNT(*) AS response_count, ROUND(AVG(score), 2) AS average_score,
       ROUND(100.0 * (COUNT_IF(score >= 9) - COUNT_IF(score <= 6)) / NULLIF(COUNT(*), 0), 2) AS nps
FROM BOOTCAMP_DB.NOVAMART.NPS_RESPONSES
WHERE response_date >= '2024-10-01' AND response_date < '2025-01-01'
GROUP BY user_segment ORDER BY user_segment""",
        "user_segment", "nps",
        "Investigate the response themes and response coverage for the lowest-NPS segment before treating the recorded responses as representative of all customers.",
        primary_direction="min",
    ),
    Case(
        "novamart-session-conversion-device-005", "product", "funnel_review", "high",
        "multi_table", "unreliable_field", "NovaMart product analytics lead",
        "Compare observed Q4 completed-order session rates across devices.",
        "Compare Q4 2024 session performance by SESSIONS.DEVICE. Report distinct session count, distinct sessions linked by SESSION_ID to at least one completed Q4 order, and the resulting completed-order session rate. Do not use SESSIONS.HAD_PURCHASE. Identify the lowest-rate device and recommend what product should investigate next without claiming causation.",
        ("SESSIONS", "ORDERS"),
        (("device", "string", 0), ("session_count", "integer", 0), ("purchasing_session_count", "integer", 0), ("completed_order_session_rate_pct", "decimal", 0.0001)),
        ("device",),
        """SELECT s.device, COUNT(DISTINCT s.session_id) AS session_count,
       COUNT(DISTINCT IFF(o.order_id IS NOT NULL, s.session_id, NULL)) AS purchasing_session_count,
       ROUND(100.0 * COUNT(DISTINCT IFF(o.order_id IS NOT NULL, s.session_id, NULL)) / NULLIF(COUNT(DISTINCT s.session_id), 0), 4) AS completed_order_session_rate_pct
FROM BOOTCAMP_DB.NOVAMART.SESSIONS s
LEFT JOIN BOOTCAMP_DB.NOVAMART.ORDERS o ON s.session_id = o.session_id
 AND o.status = 'completed' AND o.order_date >= '2024-10-01' AND o.order_date < '2025-01-01'
WHERE s.session_date >= '2024-10-01' AND s.session_date < '2025-01-01'
GROUP BY s.device ORDER BY s.device""",
        "device", "completed_order_session_rate_pct",
        "Investigate funnel-stage behavior and traffic mix for the lowest-rate device before proposing a product change.",
        primary_direction="min",
    ),
    Case(
        "novamart-plus-order-value-006", "membership", "segment_review", "low",
        "single_table", "directionality", "NovaMart membership lead",
        "Describe the Q4 completed-order value difference between Plus and non-Plus orders.",
        "Compare completed NovaMart orders from October 1, 2024 inclusive through January 1, 2025 exclusive by IS_PLUS_MEMBER_ORDER. Report completed-order count, completed-order value, and average completed-order value for Plus and non-Plus orders. Identify which group has higher average order value and recommend what membership should investigate next. Do not claim membership caused the difference.",
        ("ORDERS",),
        (("member_group", "string", 0), ("completed_order_count", "integer", 0), ("completed_order_value", "decimal", 0.01), ("average_completed_order_value", "decimal", 0.01)),
        ("member_group",),
        """SELECT IFF(is_plus_member_order, 'Plus', 'Non-Plus') AS member_group,
       COUNT(*) AS completed_order_count, ROUND(SUM(total_amount), 2) AS completed_order_value,
       ROUND(AVG(total_amount), 2) AS average_completed_order_value
FROM BOOTCAMP_DB.NOVAMART.ORDERS
WHERE status = 'completed' AND order_date >= '2024-10-01' AND order_date < '2025-01-01'
GROUP BY 1 ORDER BY 1""",
        "member_group", "average_completed_order_value",
        "Investigate customer and product mix behind the observed average-order-value difference rather than attributing it to membership status.",
    ),
    Case(
        "novamart-repeat-purchase-channel-007", "growth", "segment_review", "high",
        "multi_table", "unit_of_analysis", "NovaMart growth lead",
        "Identify acquisition channels with different Q4 repeat-purchase behavior.",
        "For users with at least one completed NovaMart order in Q4 2024, compare repeat-purchase rate by USERS.ACQUISITION_CHANNEL. Define a repeat purchaser as a user with at least two completed Q4 orders. Report purchaser count, repeat-purchaser count, and repeat-purchase rate. Identify the highest-rate channel and recommend what growth should investigate next. Do not claim the channel caused repeat purchasing.",
        ("USERS", "ORDERS"),
        (("acquisition_channel", "string", 0), ("purchaser_count", "integer", 0), ("repeat_purchaser_count", "integer", 0), ("repeat_purchase_rate_pct", "decimal", 0.01)),
        ("acquisition_channel",),
        """WITH user_orders AS (
  SELECT user_id, COUNT(*) AS completed_orders
  FROM BOOTCAMP_DB.NOVAMART.ORDERS
  WHERE status = 'completed' AND order_date >= '2024-10-01' AND order_date < '2025-01-01'
  GROUP BY user_id
)
SELECT u.acquisition_channel, COUNT(*) AS purchaser_count,
       COUNT_IF(o.completed_orders >= 2) AS repeat_purchaser_count,
       ROUND(100.0 * COUNT_IF(o.completed_orders >= 2) / NULLIF(COUNT(*), 0), 2) AS repeat_purchase_rate_pct
FROM user_orders o JOIN BOOTCAMP_DB.NOVAMART.USERS u ON o.user_id = u.user_id
GROUP BY u.acquisition_channel ORDER BY u.acquisition_channel""",
        "acquisition_channel", "repeat_purchase_rate_pct",
        "Investigate customer mix, order timing, and offer exposure in the highest-rate channel before reallocating acquisition spend.",
    ),
    Case(
        "novamart-support-category-008", "support", "segment_review", "medium",
        "single_table", "missingness", "NovaMart support manager",
        "Identify Q4 support categories combining high volume and slow resolution.",
        "Compare Q4 2024 support tickets by CATEGORY. Report ticket count, resolved-ticket count, and median resolution hours among resolved tickets. Identify the category with the highest ticket count and note whether it also has the slowest median resolution. Recommend what support should investigate next while keeping unresolved tickets visible as a limitation.",
        ("SUPPORT_TICKETS",),
        (("category", "string", 0), ("ticket_count", "integer", 0), ("resolved_ticket_count", "integer", 0), ("median_resolution_hours", "decimal", 0.01)),
        ("category",),
        """SELECT category, COUNT(*) AS ticket_count, COUNT_IF(resolved_at IS NOT NULL) AS resolved_ticket_count,
       ROUND(MEDIAN(IFF(resolved_at IS NOT NULL, DATEDIFF('minute', created_at, resolved_at) / 60.0, NULL)), 2) AS median_resolution_hours
FROM BOOTCAMP_DB.NOVAMART.SUPPORT_TICKETS
WHERE created_date >= '2024-10-01' AND created_date < '2025-01-01'
GROUP BY category ORDER BY category""",
        "category", "ticket_count",
        "Investigate the drivers of the highest-volume category and separately examine categories with slow resolution rather than assuming volume explains duration.",
    ),
    Case(
        "novamart-search-session-009", "product", "funnel_review", "high",
        "multi_table", "join_grain", "NovaMart product lead",
        "Compare completed-order session rates for Q4 sessions with and without search activity.",
        "Classify each Q4 2024 NovaMart session as searched or did_not_search based on whether EVENTS contains at least one search event for that SESSION_ID. Report session count, distinct sessions linked to a completed Q4 order, and completed-order session rate for each group. Recommend what product should investigate next without interpreting this descriptive comparison as a causal effect of search.",
        ("SESSIONS", "EVENTS", "ORDERS"),
        (("search_group", "string", 0), ("session_count", "integer", 0), ("purchasing_session_count", "integer", 0), ("completed_order_session_rate_pct", "decimal", 0.0001)),
        ("search_group",),
        """WITH session_flags AS (
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
GROUP BY f.search_group ORDER BY f.search_group""",
        "search_group", "completed_order_session_rate_pct",
        "Investigate query intent, traffic mix, and the downstream funnel before concluding that search itself changes purchase behavior.",
    ),
    Case(
        "novamart-promotion-returns-010", "marketing", "campaign_review", "medium",
        "multi_table", "population", "NovaMart marketing lead",
        "Compare return behavior across named Q4 promotions.",
        "Compare Black Friday and Holiday Sale orders by PROMO_ID for their promotion date windows. Report completed-order count, returned-order count, returned share among completed plus returned orders, completed-order value, and returned-order value. Identify which promotion has the higher returned share and recommend what marketing should investigate before repeating either promotion. Do not claim the promotion caused returns.",
        ("ORDERS", "PROMOTIONS"),
        (("promo_name", "string", 0), ("completed_order_count", "integer", 0), ("returned_order_count", "integer", 0), ("returned_share_pct", "decimal", 0.01), ("completed_order_value", "decimal", 0.01), ("returned_order_value", "decimal", 0.01)),
        ("promo_name",),
        """SELECT p.promo_name,
       COUNT_IF(o.status = 'completed') AS completed_order_count,
       COUNT_IF(o.status = 'returned') AS returned_order_count,
       ROUND(100.0 * COUNT_IF(o.status = 'returned') / NULLIF(COUNT_IF(o.status IN ('completed','returned')), 0), 2) AS returned_share_pct,
       ROUND(SUM(IFF(o.status = 'completed', o.total_amount, 0)), 2) AS completed_order_value,
       ROUND(SUM(IFF(o.status = 'returned', o.total_amount, 0)), 2) AS returned_order_value
FROM BOOTCAMP_DB.NOVAMART.PROMOTIONS p
JOIN BOOTCAMP_DB.NOVAMART.ORDERS o ON p.promo_id = o.promo_id
WHERE p.promo_name IN ('Black Friday','Holiday Sale') AND o.order_date BETWEEN p.start_date AND p.end_date
GROUP BY p.promo_name ORDER BY p.promo_name""",
        "promo_name", "returned_share_pct",
        "Investigate product, customer, and discount mix behind the higher returned share before changing promotion strategy.",
    ),
    Case(
        "novamart-category-profit-011", "merchandising", "profitability_review", "high",
        "multi_table", "join_grain", "NovaMart merchandising lead",
        "Compare Q4 completed-order merchandise gross profit across product categories.",
        "For completed orders from October 1, 2024 inclusive through January 1, 2025 exclusive, compare product categories using ORDER_ITEMS and PRODUCTS. Report units, merchandise value, merchandise cost, merchandise gross profit, and gross margin percentage. Define merchandise gross profit as LINE_TOTAL minus QUANTITY times PRODUCTS.COST. Identify the category with the highest gross profit and recommend what merchandising should investigate next. Do not sum order-level TOTAL_AMOUNT after joining to item rows.",
        ("ORDERS", "ORDER_ITEMS", "PRODUCTS"),
        (("category", "string", 0), ("units", "integer", 0), ("merchandise_value", "decimal", 0.01), ("merchandise_cost", "decimal", 0.01), ("merchandise_gross_profit", "decimal", 0.01), ("gross_margin_pct", "decimal", 0.01)),
        ("category",),
        """SELECT p.category, SUM(oi.quantity) AS units,
       ROUND(SUM(oi.line_total), 2) AS merchandise_value,
       ROUND(SUM(oi.quantity * p.cost), 2) AS merchandise_cost,
       ROUND(SUM(oi.line_total - oi.quantity * p.cost), 2) AS merchandise_gross_profit,
       ROUND(100.0 * SUM(oi.line_total - oi.quantity * p.cost) / NULLIF(SUM(oi.line_total), 0), 2) AS gross_margin_pct
FROM BOOTCAMP_DB.NOVAMART.ORDERS o
JOIN BOOTCAMP_DB.NOVAMART.ORDER_ITEMS oi ON o.order_id = oi.order_id
JOIN BOOTCAMP_DB.NOVAMART.PRODUCTS p ON oi.product_id = p.product_id
WHERE o.status = 'completed' AND o.order_date >= '2024-10-01' AND o.order_date < '2025-01-01'
GROUP BY p.category ORDER BY p.category""",
        "category", "merchandise_gross_profit",
        "Investigate volume, product mix, discounting, and margin rate in the highest-profit category before changing assortment.",
    ),
    Case(
        "novamart-acquisition-performance-012", "growth", "segment_review", "high",
        "multi_table", "unit_of_analysis", "NovaMart growth lead",
        "Compare Q4 completed-purchase performance across acquisition channels.",
        "For NovaMart users with completed orders in Q4 2024, compare USERS.ACQUISITION_CHANNEL. Report distinct purchasers, completed orders, completed-order value, and average completed-order value. Identify the channel with the highest completed-order value and recommend what growth should investigate next. Do not treat the descriptive result as channel incrementality or return on ad spend.",
        ("USERS", "ORDERS"),
        (("acquisition_channel", "string", 0), ("purchaser_count", "integer", 0), ("completed_order_count", "integer", 0), ("completed_order_value", "decimal", 0.01), ("average_completed_order_value", "decimal", 0.01)),
        ("acquisition_channel",),
        """SELECT u.acquisition_channel, COUNT(DISTINCT o.user_id) AS purchaser_count,
       COUNT(*) AS completed_order_count, ROUND(SUM(o.total_amount), 2) AS completed_order_value,
       ROUND(AVG(o.total_amount), 2) AS average_completed_order_value
FROM BOOTCAMP_DB.NOVAMART.ORDERS o JOIN BOOTCAMP_DB.NOVAMART.USERS u ON o.user_id = u.user_id
WHERE o.status = 'completed' AND o.order_date >= '2024-10-01' AND o.order_date < '2025-01-01'
GROUP BY u.acquisition_channel ORDER BY u.acquisition_channel""",
        "acquisition_channel", "completed_order_value",
        "Investigate purchaser volume, repeat behavior, customer mix, and acquisition cost before changing channel investment.",
    ),
    Case(
        "novamart-app-version-support-013", "product", "quality_review", "medium",
        "single_table", "missingness", "NovaMart mobile product lead",
        "Identify app versions associated with Q4 high-severity support burden.",
        "Compare Q4 2024 support tickets by APP_VERSION, retaining missing versions as unknown. Report ticket count, high-or-critical ticket count, high-or-critical share, and median resolution hours among resolved tickets. Identify the known app version with the highest high-or-critical share and recommend what product should investigate next. Do not claim the version caused the tickets.",
        ("SUPPORT_TICKETS",),
        (("app_version", "string", 0), ("ticket_count", "integer", 0), ("high_critical_count", "integer", 0), ("high_critical_share_pct", "decimal", 0.01), ("median_resolution_hours", "decimal", 0.01)),
        ("app_version",),
        """SELECT COALESCE(app_version, 'unknown') AS app_version, COUNT(*) AS ticket_count,
       COUNT_IF(severity IN ('high','critical')) AS high_critical_count,
       ROUND(100.0 * COUNT_IF(severity IN ('high','critical')) / NULLIF(COUNT(*), 0), 2) AS high_critical_share_pct,
       ROUND(MEDIAN(IFF(resolved_at IS NOT NULL, DATEDIFF('minute', created_at, resolved_at) / 60.0, NULL)), 2) AS median_resolution_hours
FROM BOOTCAMP_DB.NOVAMART.SUPPORT_TICKETS
WHERE created_date >= '2024-10-01' AND created_date < '2025-01-01'
GROUP BY COALESCE(app_version, 'unknown') ORDER BY app_version""",
        "app_version", "high_critical_share_pct",
        "Investigate issue categories and user exposure for the highest-share known version while treating missing version data separately.",
        excluded_labels=("unknown",),
    ),
    Case(
        "novamart-weekend-orders-014", "operations", "segment_review", "medium",
        "multi_table", "date_mapping", "NovaMart operations lead",
        "Compare Q4 completed-order performance on weekends and weekdays.",
        "Join ORDERS to CALENDAR by ORDER_DATE for Q4 2024 completed orders. Report completed-order count, completed-order value, and average completed-order value for weekend and weekday. Identify which day type has higher average order value and recommend what operations should investigate next. Do not claim day type caused the difference.",
        ("ORDERS", "CALENDAR"),
        (("day_type", "string", 0), ("completed_order_count", "integer", 0), ("completed_order_value", "decimal", 0.01), ("average_completed_order_value", "decimal", 0.01)),
        ("day_type",),
        """SELECT IFF(c.is_weekend, 'weekend', 'weekday') AS day_type,
       COUNT(*) AS completed_order_count, ROUND(SUM(o.total_amount), 2) AS completed_order_value,
       ROUND(AVG(o.total_amount), 2) AS average_completed_order_value
FROM BOOTCAMP_DB.NOVAMART.ORDERS o JOIN BOOTCAMP_DB.NOVAMART.CALENDAR c ON o.order_date = c.date
WHERE o.status = 'completed' AND o.order_date >= '2024-10-01' AND o.order_date < '2025-01-01'
GROUP BY 1 ORDER BY 1""",
        "day_type", "average_completed_order_value",
        "Investigate product, promotion, and customer mix behind the observed day-type difference before changing operating plans.",
    ),
    Case(
        "novamart-new-repeat-purchasers-015", "growth", "cohort_review", "high",
        "multi_table", "time_boundary", "NovaMart growth lead",
        "Understand the mix of first-time and returning completed purchasers across Q4.",
        "For each month in Q4 2024, report distinct completed purchasers, first-time completed purchasers whose first-ever completed order occurred in that month, returning completed purchasers, and first-time share. Use all available order history to establish each user's first completed order. Identify the month with the highest first-time share and recommend what growth should investigate next.",
        ("ORDERS",),
        (("month", "string", 0), ("completed_purchasers", "integer", 0), ("first_time_purchasers", "integer", 0), ("returning_purchasers", "integer", 0), ("first_time_share_pct", "decimal", 0.01)),
        ("month",),
        """WITH first_completed AS (
  SELECT user_id, MIN(order_date) AS first_completed_date
  FROM BOOTCAMP_DB.NOVAMART.ORDERS WHERE status = 'completed' GROUP BY user_id
), monthly AS (
  SELECT DATE_TRUNC('month', o.order_date)::DATE AS month, o.user_id,
         IFF(DATE_TRUNC('month', f.first_completed_date) = DATE_TRUNC('month', o.order_date), 1, 0) AS is_first_time
  FROM BOOTCAMP_DB.NOVAMART.ORDERS o JOIN first_completed f ON o.user_id = f.user_id
  WHERE o.status = 'completed' AND o.order_date >= '2024-10-01' AND o.order_date < '2025-01-01'
  GROUP BY month, o.user_id, is_first_time
)
SELECT TO_CHAR(month, 'YYYY-MM') AS month, COUNT(*) AS completed_purchasers,
       COUNT_IF(is_first_time = 1) AS first_time_purchasers,
       COUNT_IF(is_first_time = 0) AS returning_purchasers,
       ROUND(100.0 * COUNT_IF(is_first_time = 1) / NULLIF(COUNT(*), 0), 2) AS first_time_share_pct
FROM monthly GROUP BY month ORDER BY month""",
        "month", "first_time_share_pct",
        "Investigate acquisition sources and purchase timing behind the highest first-time share without interpreting the mix as retention.",
    ),
    Case(
        "novamart-membership-cancellation-016", "membership", "retention_review", "medium",
        "single_table", "population", "NovaMart membership lead",
        "Understand Q4 membership endings and cancellation reasons.",
        "For membership records with ENDED_AT from October 1, 2024 inclusive through January 1, 2025 exclusive, compare CANCEL_REASON, retaining missing values as unknown. Report ended membership count and average tenure days from STARTED_AT to ENDED_AT. Identify the largest stated cancellation-reason group and recommend what membership should investigate next. Do not call this a retention rate.",
        ("MEMBERSHIPS",),
        (("cancel_reason", "string", 0), ("ended_membership_count", "integer", 0), ("average_tenure_days", "decimal", 0.01)),
        ("cancel_reason",),
        """SELECT COALESCE(cancel_reason, 'unknown') AS cancel_reason,
       COUNT(*) AS ended_membership_count,
       ROUND(AVG(DATEDIFF('day', started_at, ended_at)), 2) AS average_tenure_days
FROM BOOTCAMP_DB.NOVAMART.MEMBERSHIPS
WHERE ended_at >= '2024-10-01' AND ended_at < '2025-01-01'
GROUP BY COALESCE(cancel_reason, 'unknown') ORDER BY cancel_reason""",
        "cancel_reason", "ended_membership_count",
        "Investigate the experiences and tenure distribution behind the largest stated reason while keeping missing reasons separate.",
        excluded_labels=("unknown",),
    ),
    Case(
        "novamart-checkout-experiment-017", "experimentation", "experiment_readout", "high",
        "multi_table", "exposure_window", "NovaMart experimentation lead",
        "Compare observed completed-purchase outcomes for the checkout redesign experiment.",
        "For the completed checkout_redesign experiment, compare variants using assigned users. Report assigned users, users with at least one completed order from FIRST_EXPOSURE_DATE through the experiment END_DATE inclusive, completed-purchaser rate, and completed-order value during that window. Identify the higher observed purchaser-rate variant and recommend the next evaluation step. This descriptive readout must not by itself claim statistical significance or approve launch.",
        ("EXPERIMENTS", "EXPERIMENT_ASSIGNMENTS", "ORDERS"),
        (("variant", "string", 0), ("assigned_users", "integer", 0), ("completed_purchasers", "integer", 0), ("completed_purchaser_rate_pct", "decimal", 0.01), ("completed_order_value", "decimal", 0.01)),
        ("variant",),
        """WITH assigned AS (
  SELECT a.user_id, a.variant, a.first_exposure_date, e.end_date
  FROM BOOTCAMP_DB.NOVAMART.EXPERIMENT_ASSIGNMENTS a
  JOIN BOOTCAMP_DB.NOVAMART.EXPERIMENTS e ON a.experiment_id = e.experiment_id
  WHERE e.experiment_name = 'checkout_redesign'
), user_outcomes AS (
  SELECT a.variant, a.user_id,
         MAX(IFF(o.order_id IS NOT NULL, 1, 0)) AS purchased,
         COALESCE(SUM(o.total_amount), 0) AS completed_order_value
  FROM assigned a LEFT JOIN BOOTCAMP_DB.NOVAMART.ORDERS o ON a.user_id = o.user_id
   AND o.status = 'completed' AND o.order_date >= a.first_exposure_date AND o.order_date <= a.end_date
  GROUP BY a.variant, a.user_id
)
SELECT variant, COUNT(*) AS assigned_users, SUM(purchased) AS completed_purchasers,
       ROUND(100.0 * SUM(purchased) / NULLIF(COUNT(*), 0), 2) AS completed_purchaser_rate_pct,
       ROUND(SUM(completed_order_value), 2) AS completed_order_value
FROM user_outcomes GROUP BY variant ORDER BY variant""",
        "variant", "completed_purchaser_rate_pct",
        "Run the planned statistical evaluation, check assignment quality and guardrails, and review uncertainty before making a launch decision.",
    ),
    Case(
        "novamart-cancellation-device-018", "operations", "segment_review", "low",
        "single_table", "denominator", "NovaMart operations lead",
        "Compare Q4 cancellation rates across ordering devices.",
        "Compare NovaMart Q4 2024 orders by DEVICE. Report total order count, cancelled-order count, and cancelled-order rate. Identify the device with the highest cancellation rate and recommend what operations should investigate next. Use all order statuses in the denominator and do not claim the device caused cancellation.",
        ("ORDERS",),
        (("device", "string", 0), ("order_count", "integer", 0), ("cancelled_order_count", "integer", 0), ("cancelled_order_rate_pct", "decimal", 0.01)),
        ("device",),
        """SELECT device, COUNT(*) AS order_count, COUNT_IF(status = 'cancelled') AS cancelled_order_count,
       ROUND(100.0 * COUNT_IF(status = 'cancelled') / NULLIF(COUNT(*), 0), 2) AS cancelled_order_rate_pct
FROM BOOTCAMP_DB.NOVAMART.ORDERS
WHERE order_date >= '2024-10-01' AND order_date < '2025-01-01'
GROUP BY device ORDER BY device""",
        "device", "cancelled_order_rate_pct",
        "Investigate checkout failures, payment issues, traffic mix, and app or browser versions for the highest-rate device.",
    ),
    Case(
        "novamart-device-funnel-019", "product", "funnel_review", "high",
        "multi_table", "event_grain", "NovaMart product lead",
        "Compare key Q4 funnel reach across session devices.",
        "For Q4 2024 sessions, compare devices by distinct session count, sessions with at least one product_view event, sessions with at least one add_to_cart event, and sessions linked to at least one completed Q4 order. Report counts at each stage. Identify where the largest proportional drop occurs for the weakest device and recommend what product should investigate next. Do not sum event rows as sessions.",
        ("SESSIONS", "EVENTS", "ORDERS"),
        (("device", "string", 0), ("session_count", "integer", 0), ("product_view_sessions", "integer", 0), ("add_to_cart_sessions", "integer", 0), ("purchasing_sessions", "integer", 0), ("completed_order_session_rate_pct", "decimal", 0.0001)),
        ("device",),
        """WITH event_flags AS (
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
GROUP BY s.device ORDER BY s.device""",
        "device", "completed_order_session_rate_pct",
        "Investigate the stage-specific drop and traffic mix for the weakest device before changing the product funnel.",
        primary_direction="min",
    ),
    Case(
        "novamart-holiday-order-mix-020", "finance", "recurring_review", "medium",
        "single_table", "status_treatment", "NovaMart finance lead",
        "Understand how completed, returned, and cancelled order value changed across Q4.",
        "Prepare a Q4 monthly order-status review. For October, November, and December 2024, report completed-order value, returned-order value, and cancelled-order value using TOTAL_AMOUNT. Identify the month with the highest returned-order value and recommend what finance should investigate next. Keep each status separate and do not call any one of these fields revenue.",
        ("ORDERS",),
        (("month", "string", 0), ("completed_order_value", "decimal", 0.01), ("returned_order_value", "decimal", 0.01), ("cancelled_order_value", "decimal", 0.01)),
        ("month",),
        """SELECT TO_CHAR(DATE_TRUNC('month', order_date), 'YYYY-MM') AS month,
       ROUND(SUM(IFF(status = 'completed', total_amount, 0)), 2) AS completed_order_value,
       ROUND(SUM(IFF(status = 'returned', total_amount, 0)), 2) AS returned_order_value,
       ROUND(SUM(IFF(status = 'cancelled', total_amount, 0)), 2) AS cancelled_order_value
FROM BOOTCAMP_DB.NOVAMART.ORDERS
WHERE order_date >= '2024-10-01' AND order_date < '2025-01-01'
GROUP BY 1 ORDER BY 1""",
        "month", "returned_order_value",
        "Investigate product, customer, and promotion mix behind the highest returned-order value before drawing a financial conclusion.",
    ),
)


def _plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


def _connection():
    load_dotenv(ANALYST_ROOT / ".env")
    kwargs = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database": os.environ["SNOWFLAKE_DATABASE"],
        "role": os.environ["SNOWFLAKE_ROLE"],
        "schema": "NOVAMART",
    }
    auth = os.getenv("SNOWFLAKE_AUTHENTICATOR", "password").upper().replace("-", "_")
    if auth in {"PROGRAMMATIC_ACCESS_TOKEN", "PAT"}:
        kwargs.update(authenticator="PROGRAMMATIC_ACCESS_TOKEN", token=os.environ["SNOWFLAKE_TOKEN"])
    else:
        kwargs["password"] = os.environ["SNOWFLAKE_PASSWORD"]
    return snowflake.connector.connect(**kwargs)


def _schema(case: Case) -> dict[str, Any]:
    row_properties = {
        name: {"type": "string" if kind == "string" else "integer" if kind == "integer" else "number"}
        for name, kind, _ in case.columns
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"{case.case_id} result",
        "type": "object",
        "additionalProperties": False,
        "required": ["case_id", "results", "final_answer", "methodology", "artifacts"],
        "properties": {
            "case_id": {"const": case.case_id},
            "results": {
                "type": "array", "minItems": 1, "maxItems": 50,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": [name for name, _, _ in case.columns],
                    "properties": row_properties,
                },
            },
            "final_answer": {
                "type": "object", "additionalProperties": False,
                "required": ["conclusion", "recommended_next_step", "supporting_facts", "important_limitation"],
                "properties": {
                    "conclusion": {"type": "string", "minLength": 20},
                    "recommended_next_step": {"type": "string", "minLength": 20},
                    "supporting_facts": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    "important_limitation": {"type": "string", "minLength": 20},
                },
            },
            "methodology": {
                "type": "object", "additionalProperties": True,
                "required": ["analysis_type", "population", "calculation_summary", "validation_checks", "assumptions"],
                "properties": {
                    "analysis_type": {"type": "string"},
                    "population": {"type": "string"},
                    "calculation_summary": {"type": "string"},
                    "validation_checks": {"type": "array", "items": {"type": "string"}},
                    "assumptions": {"type": "array", "items": {"type": "string"}},
                },
            },
            "artifacts": {
                "type": "object", "additionalProperties": False,
                "required": ["results", "brief", "chart", "chart_data", "calculation"],
                "properties": {
                    "results": {"const": "results.csv"}, "brief": {"const": "brief.md"},
                    "chart": {"const": "chart.png"}, "chart_data": {"const": "chart-data.csv"},
                    "calculation": {"const": "calculation.sql"},
                },
            },
        },
    }


def _public_case(case: Case) -> dict[str, Any]:
    column_names = [name for name, _, _ in case.columns]
    return {
        "schema_version": "1", "case_id": case.case_id, "case_version": "1",
        "status": "proposed", "exposure": "development",
        "slices": {
            "domain": case.domain, "task_type": case.task_type, "complexity": case.complexity,
            "data_shape": case.data_shape, "primary_risk": case.risk,
        },
        "audience": case.audience, "decision": case.decision,
        "data_scope": {
            "platform": "Snowflake", "database": "BOOTCAMP_DB", "schema": "NOVAMART",
            "tables": list(case.tables), "snapshot_id": "novamart-all-tables-2026-09-24-v1",
            "snapshot_fingerprint": {
                "method": "sha256_of_ordered_table_row_counts", "sha256": SNAPSHOT_SHA256,
                "query": SNAPSHOT_QUERY,
            },
        },
        "task": case.task,
        "required_outputs": ["result.json", "results.csv", "brief.md", "chart.png", "chart-data.csv", "calculation.sql"],
        "result_schema": "result.schema.json",
        "output_contract": {
            "csv": [
                {"path": "results.csv", "columns": column_names, "min_rows": 1, "max_rows": 50},
                {"path": "chart-data.csv", "columns": column_names, "min_rows": 1, "max_rows": 50},
            ],
            "text": {"path": "brief.md", "min_characters": 100},
            "image": {"path": "chart.png", "min_width": 400, "min_height": 250},
            "sql": {"path": "calculation.sql"},
        },
        "grading_contract": {
            "reference_in_student_repository": False,
            "headline_gates": ["output_contract", "deterministic_accuracy", "final_answer_judge"],
            "diagnostic_only": ["source_selection", "population", "date_boundary", "query_correctness", "validation_checks", "query_to_finding_linkage", "trace_completeness"],
        },
    }


def _private_grading(case: Case) -> dict[str, Any]:
    rules = {
        name: {"type": kind, **({"absolute_tolerance": tolerance} if kind == "decimal" else {})}
        for name, kind, tolerance in case.columns
    }
    sources = [f"BOOTCAMP_DB.NOVAMART.{table}" for table in case.tables]
    return {
        "schema_version": "1", "case_id": case.case_id, "case_version": "1",
        "artifact_contract": {
            "required_files": ["result.json", "results.csv", "brief.md", "chart.png", "chart-data.csv", "calculation.sql"],
            "exact_file_set": True,
            "result_json": {"path": "result.json", "case_id": case.case_id, "required_sections": ["case_id", "results", "final_answer", "methodology", "artifacts"]},
            "csv": [
                {"id": "results", "path": "results.csv", "columns": list(rules), "min_rows": 1, "max_rows": 50},
                {"id": "chart_data", "path": "chart-data.csv", "columns": list(rules), "min_rows": 1, "max_rows": 50},
            ],
            "image": {"path": "chart.png", "min_width": 400, "min_height": 250},
            "text": {"path": "brief.md", "min_characters": 100},
        },
        "query_outputs": [{
            "output_id": "results", "submission_sql": "calculation.sql", "reference_sql": "reference.sql",
            "submitted_table": "results.csv", "allowed_sources": sources, "timeout_seconds": 120, "max_rows": 500,
            "comparison": {"mode": "keyed_table", "keys": list(case.keys), "columns": rules},
        }],
        "cross_artifact_tables": [
            {"id": "chart_data_matches_results", "left": {"type": "csv", "path": "results.csv"}, "right": {"type": "csv", "path": "chart-data.csv"}, "comparison": {"mode": "keyed_table", "keys": list(case.keys), "columns": rules}},
            {"id": "result_json_matches_results", "left": {"type": "csv", "path": "results.csv"}, "right": {"type": "json_table", "path": "result.json", "field": "results"}, "comparison": {"mode": "keyed_table", "keys": list(case.keys), "columns": rules}},
        ],
        "model_graders": [{
            "id": "final_answer.v1", "rubric": "course_evals/graders/model/final_answer/v1/rubric.md",
            "evidence": {"result_json_field": "final_answer", "brief": "brief.md"},
            "criteria_reference_field": "accepted_final_answer", "blocking": True,
        }],
        "diagnostics": ["source_selection", "population", "date_boundary", "query_correctness", "validation_checks", "query_to_finding_linkage", "trace_completeness"],
        "headline": {"required": ["artifact_contract", "sql_result", "cross_artifact_consistency", "final_answer.v1"]},
    }


def build() -> None:
    if not ANALYST_ROOT.is_dir():
        raise SystemExit(f"AI Analyst sibling repository not found: {ANALYST_ROOT}")
    suite_entries = [
        {"case_id": "novamart-monthly-operating-review-001", "case_version": "1", "path": "evals/cases/public/novamart-monthly-operating-review-001/v1"},
    ]
    with _connection() as connection:
        with connection.cursor() as cursor:
            for case in CASES:
                cursor.execute(case.sql)
                names = [str(item[0]).lower() for item in cursor.description]
                rows = [_plain(dict(zip(names, row, strict=True))) for row in cursor.fetchall()]
                if not rows:
                    raise ValueError(f"reference query returned no rows: {case.case_id}")
                eligible = [
                    row for row in rows
                    if str(row[case.primary_label]) not in set(case.excluded_labels)
                ]
                if not eligible:
                    raise ValueError(f"no eligible headline rows: {case.case_id}")
                chooser = min if case.primary_direction == "min" else max
                top = chooser(eligible, key=lambda row: float(row[case.primary_metric]))
                extreme_value = float(top[case.primary_metric])
                tied_labels = sorted(
                    str(row[case.primary_label])
                    for row in eligible
                    if float(row[case.primary_metric]) == extreme_value
                )
                direction_word = "lowest" if case.primary_direction == "min" else "highest"
                if len(tied_labels) == 1:
                    conclusion = (
                        f"The answer correctly identifies {tied_labels[0]} as the {direction_word} observed "
                        f"{case.primary_metric.replace('_', ' ')} and reports the reviewed values without "
                        "material contradiction."
                    )
                else:
                    joined_labels = ", ".join(tied_labels[:-1]) + f" and {tied_labels[-1]}"
                    conclusion = (
                        f"The answer correctly identifies {joined_labels} as tied for the {direction_word} "
                        f"observed {case.primary_metric.replace('_', ' ')} and reports the reviewed values "
                        "without material contradiction."
                    )
                public_root = ANALYST_ROOT / "evals" / "cases" / "public" / case.case_id / "v1"
                public_root.mkdir(parents=True, exist_ok=True)
                (public_root / "case.yaml").write_text(yaml.safe_dump(_public_case(case), sort_keys=False, width=100), encoding="utf-8")
                (public_root / "result.schema.json").write_text(json.dumps(_schema(case), indent=2) + "\n", encoding="utf-8")
                (public_root / "README.md").write_text(
                    f"# {case.case_id}\n\nThis directory contains the student-visible task and output contract. "
                    "The evaluation materials used after a run is locked are maintained separately.\n",
                    encoding="utf-8",
                )

                private_root = ROOT / "cases" / case.case_id
                private_root.mkdir(parents=True, exist_ok=True)
                (private_root / "reference.sql").write_text(case.sql.strip() + ";\n", encoding="utf-8")
                reference = {
                    "case_id": case.case_id, "case_version": "1", "status": "proposed",
                    "visibility": "private-reference", "verified_at": date.today().isoformat(),
                    "review_status": "computationally_verified_pending_instructor_review",
                    "slices": _public_case(case)["slices"],
                    "source": {"platform": "snowflake", "database": "BOOTCAMP_DB", "schema": "NOVAMART", "tables": list(case.tables), "table_fingerprint": {"method": "sha256_of_ordered_table_row_counts", "value": SNAPSHOT_SHA256}},
                    "expected": {"results": rows},
                    "accepted_final_answer": {
                        "required_conclusion": [conclusion],
                        "required_recommendation": [case.recommendation],
                        "acceptable_semantic_variation": True,
                        "prohibited_claims": list(case.prohibited_claims),
                    },
                    "headline_grade": {"output_contract_required": True, "deterministic_accuracy_required": True, "final_answer_judge_required": True, "formula": "output_contract AND deterministic_accuracy AND final_answer_judge"},
                }
                (private_root / "reference.yaml").write_text(yaml.safe_dump(reference, sort_keys=False, width=100), encoding="utf-8")
                (private_root / "grading.yaml").write_text(yaml.safe_dump(_private_grading(case), sort_keys=False, width=100), encoding="utf-8")
                suite_entries.append({"case_id": case.case_id, "case_version": "1", "path": f"evals/cases/public/{case.case_id}/v1"})

    suite = {
        "suite_id": "session-6-complete-analysis-development", "suite_version": "1",
        "purpose": "Measure complete analytical workflow performance across representative NovaMart work.",
        "data_snapshot": "novamart-all-tables-2026-09-24-v1", "cases": suite_entries,
    }
    suite_path = ANALYST_ROOT / "evals" / "suites" / "session-6-complete-analysis.yaml"
    suite_path.write_text(yaml.safe_dump(suite, sort_keys=False, width=100), encoding="utf-8")
    print(f"Wrote {len(suite_entries)} complete-analysis cases to {suite_path}")


if __name__ == "__main__":
    build()

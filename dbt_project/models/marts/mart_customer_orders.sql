-- mart_customer_orders: Customer-level order summary
-- Owner: analytics | Schedule: every 6 hours
-- Dependencies: stg_customers, stg_orders

SELECT
    c.customer_id,
    c.first_name,
    c.last_name,
    c.email,
    c.country,
    c.signup_date,
    c.is_active,
    COUNT(DISTINCT o.order_id) AS total_orders,
    COUNT(DISTINCT CASE WHEN o.status = 'completed' THEN o.order_id END) AS completed_orders,
    COUNT(DISTINCT CASE WHEN o.status = 'cancelled' THEN o.order_id END) AS cancelled_orders,
    COALESCE(SUM(CASE WHEN o.status = 'completed' THEN o.total_amount END), 0) AS lifetime_revenue,
    COALESCE(AVG(CASE WHEN o.status = 'completed' THEN o.total_amount END), 0) AS avg_order_value,
    MIN(o.order_date) AS first_order_date,
    MAX(o.order_date) AS last_order_date,
    EXTRACT(DAY FROM NOW() - MAX(o.order_date)) AS days_since_last_order,
    CURRENT_TIMESTAMP AS _computed_at
FROM {{ ref('stg_customers') }} c
LEFT JOIN {{ ref('stg_orders') }} o
    ON c.customer_id = o.customer_id
GROUP BY
    c.customer_id, c.first_name, c.last_name, c.email,
    c.country, c.signup_date, c.is_active

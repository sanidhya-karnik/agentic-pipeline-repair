-- mart_revenue_daily: Daily revenue aggregation across all products
-- Owner: analytics | Schedule: daily
-- Dependencies: stg_orders, stg_order_items, stg_products

WITH order_items_enriched AS (
    SELECT
        oi.order_id,
        oi.product_id,
        oi.quantity,
        oi.unit_price,
        oi.line_total,
        p.product_name,
        p.category,
        p.cost,
        (oi.quantity * p.cost) AS line_cost
    FROM {{ ref('stg_order_items') }} oi
    JOIN {{ ref('stg_products') }} p
        ON oi.product_id = p.product_id
),

orders_with_items AS (
    SELECT
        o.order_id,
        o.order_date,
        o.status,
        o.total_amount,
        o.shipping_cost,
        oie.product_id,
        oie.product_name,
        oie.category,
        oie.quantity,
        oie.line_total,
        oie.line_cost
    FROM {{ ref('stg_orders') }} o
    JOIN order_items_enriched oie
        ON o.order_id = oie.order_id
    WHERE o.status = 'completed'
)

SELECT
    DATE(order_date) AS revenue_date,
    COUNT(DISTINCT order_id) AS total_orders,
    SUM(quantity) AS total_units_sold,
    SUM(line_total) AS gross_revenue,
    SUM(shipping_cost) AS total_shipping,
    SUM(line_cost) AS total_cost,
    SUM(line_total) - SUM(line_cost) AS gross_profit,
    ROUND(
        (SUM(line_total) - SUM(line_cost)) / NULLIF(SUM(line_total), 0) * 100, 2
    ) AS profit_margin_pct,
    CURRENT_TIMESTAMP AS _computed_at
FROM orders_with_items
GROUP BY DATE(order_date)
ORDER BY revenue_date DESC

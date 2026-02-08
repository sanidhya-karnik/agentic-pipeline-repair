-- mart_product_performance: Product-level performance metrics
-- Owner: analytics | Schedule: daily
-- Dependencies: stg_order_items, stg_products

SELECT
    p.product_id,
    p.product_name,
    p.category,
    p.price AS current_price,
    p.cost AS current_cost,
    p.margin_pct,
    COUNT(DISTINCT oi.order_id) AS times_ordered,
    SUM(oi.quantity) AS total_units_sold,
    SUM(oi.line_total) AS total_revenue,
    SUM(oi.quantity * p.cost) AS total_cost,
    SUM(oi.line_total) - SUM(oi.quantity * p.cost) AS total_profit,
    ROUND(AVG(oi.unit_price), 2) AS avg_selling_price,
    ROUND(
        (SUM(oi.line_total) - SUM(oi.quantity * p.cost)) / NULLIF(SUM(oi.line_total), 0) * 100, 2
    ) AS realized_margin_pct,
    CURRENT_TIMESTAMP AS _computed_at
FROM {{ ref('stg_products') }} p
LEFT JOIN {{ ref('stg_order_items') }} oi
    ON p.product_id = oi.product_id
GROUP BY
    p.product_id, p.product_name, p.category,
    p.price, p.cost, p.margin_pct
ORDER BY total_revenue DESC NULLS LAST

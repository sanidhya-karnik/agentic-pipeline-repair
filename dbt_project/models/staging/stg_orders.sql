-- stg_orders: Clean and standardize order data from raw source
-- Owner: data-eng | Schedule: every 6 hours

SELECT
    order_id,
    customer_id,
    order_date,
    status,
    COALESCE(total_amount, 0) AS total_amount,
    COALESCE(shipping_cost, 0) AS shipping_cost,
    payment_method,
    CURRENT_TIMESTAMP AS _loaded_at
FROM {{ source('raw', 'orders') }}
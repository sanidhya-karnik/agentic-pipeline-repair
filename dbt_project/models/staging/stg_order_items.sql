-- stg_order_items: Clean and standardize order line items
-- Owner: data-eng | Schedule: every 6 hours

SELECT
    item_id,
    order_id,
    product_id,
    quantity,
    unit_price,
    (quantity * unit_price) AS line_total,
    CURRENT_TIMESTAMP AS _loaded_at
FROM {{ source('raw', 'order_items') }}
WHERE quantity > 0

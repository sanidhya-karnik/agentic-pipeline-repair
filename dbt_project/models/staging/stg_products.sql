-- stg_products: Clean and standardize product catalog
-- Owner: data-eng | Schedule: daily

SELECT
    product_id,
    TRIM(product_name) AS product_name,
    TRIM(category) AS category,
    price,
    cost,
    (price - cost) AS margin,
    ROUND((price - cost) / NULLIF(price, 0) * 100, 2) AS margin_pct,
    created_at,
    CURRENT_TIMESTAMP AS _loaded_at
FROM {{ source('raw', 'products') }}
WHERE price > 0

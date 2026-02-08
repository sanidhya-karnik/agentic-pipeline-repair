-- stg_customers: Clean and standardize customer data from raw source
-- Owner: data-eng | Schedule: every 6 hours

SELECT
    customer_id,
    TRIM(LOWER(first_name)) AS first_name,
    TRIM(LOWER(last_name)) AS last_name,
    LOWER(TRIM(email)) AS email,
    signup_date,
    UPPER(country) AS country,
    is_active,
    CURRENT_TIMESTAMP AS _loaded_at
FROM {{ source('raw', 'customers') }}
WHERE email IS NOT NULL

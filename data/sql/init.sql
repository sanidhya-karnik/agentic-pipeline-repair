-- ============================================================
-- Agentic Pipeline Repair: Database Initialization
-- Creates synthetic e-commerce data + pipeline monitoring tables
-- ============================================================

-- ============================================================
-- PART 1: Source e-commerce tables (simulating raw data)
-- ============================================================

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS pipeline_meta;

-- Raw customers
CREATE TABLE raw.customers (
    customer_id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    signup_date DATE NOT NULL,
    country VARCHAR(100) DEFAULT 'US',
    is_active BOOLEAN DEFAULT true
);

-- Raw products
CREATE TABLE raw.products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    cost DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Raw orders
CREATE TABLE raw.orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES raw.customers(customer_id),
    order_date TIMESTAMP NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'completed',
    total_amount DECIMAL(10,2),
    shipping_cost DECIMAL(10,2) DEFAULT 0.00,
    payment_method VARCHAR(50)
);

-- Raw order items
CREATE TABLE raw.order_items (
    item_id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES raw.orders(order_id),
    product_id INTEGER REFERENCES raw.products(product_id),
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL
);

-- ============================================================
-- PART 2: Seed synthetic data
-- ============================================================

-- Customers (50 records)
INSERT INTO raw.customers (first_name, last_name, email, signup_date, country, is_active)
SELECT
    'Customer_' || i,
    'Last_' || i,
    'customer' || i || '@example.com',
    DATE '2023-01-01' + (random() * 700)::int,
    CASE (i % 5)
        WHEN 0 THEN 'US'
        WHEN 1 THEN 'UK'
        WHEN 2 THEN 'CA'
        WHEN 3 THEN 'DE'
        WHEN 4 THEN 'FR'
    END,
    random() > 0.1
FROM generate_series(1, 50) AS i;

-- Products (20 records)
INSERT INTO raw.products (product_name, category, price, cost)
SELECT
    'Product_' || i,
    CASE (i % 4)
        WHEN 0 THEN 'Electronics'
        WHEN 1 THEN 'Clothing'
        WHEN 2 THEN 'Home & Garden'
        WHEN 3 THEN 'Books'
    END,
    (random() * 200 + 10)::decimal(10,2),
    (random() * 100 + 5)::decimal(10,2)
FROM generate_series(1, 20) AS i;

-- Orders (500 records)
INSERT INTO raw.orders (customer_id, order_date, status, total_amount, shipping_cost, payment_method)
SELECT
    (random() * 49 + 1)::int,
    TIMESTAMP '2024-01-01' + (random() * 400)::int * INTERVAL '1 day' + (random() * 86400)::int * INTERVAL '1 second',
    CASE (i % 10)
        WHEN 9 THEN 'cancelled'
        WHEN 8 THEN 'refunded'
        WHEN 7 THEN 'pending'
        ELSE 'completed'
    END,
    (random() * 500 + 20)::decimal(10,2),
    (random() * 15)::decimal(10,2),
    CASE (i % 3)
        WHEN 0 THEN 'credit_card'
        WHEN 1 THEN 'paypal'
        WHEN 2 THEN 'bank_transfer'
    END
FROM generate_series(1, 500) AS i;

-- Order items (1000+ records)
INSERT INTO raw.order_items (order_id, product_id, quantity, unit_price)
SELECT
    (random() * 499 + 1)::int,
    (random() * 19 + 1)::int,
    (random() * 5 + 1)::int,
    (random() * 200 + 10)::decimal(10,2)
FROM generate_series(1, 1200) AS i;

-- ============================================================
-- PART 3: Pipeline metadata tables (for monitoring)
-- ============================================================

-- Pipeline definitions
CREATE TABLE pipeline_meta.pipelines (
    pipeline_id SERIAL PRIMARY KEY,
    pipeline_name VARCHAR(255) NOT NULL,
    description TEXT,
    schedule VARCHAR(100),
    sla_minutes INTEGER DEFAULT 30,
    owner VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- Pipeline dependencies (DAG)
CREATE TABLE pipeline_meta.dependencies (
    id SERIAL PRIMARY KEY,
    pipeline_id INTEGER REFERENCES pipeline_meta.pipelines(pipeline_id),
    depends_on_pipeline_id INTEGER REFERENCES pipeline_meta.pipelines(pipeline_id),
    dependency_type VARCHAR(50) DEFAULT 'hard'
);

-- Pipeline run history
CREATE TABLE pipeline_meta.pipeline_runs (
    run_id SERIAL PRIMARY KEY,
    pipeline_id INTEGER REFERENCES pipeline_meta.pipelines(pipeline_id),
    status VARCHAR(50) NOT NULL, -- running, success, failed, timeout
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    row_count INTEGER,
    error_message TEXT,
    run_metadata JSONB DEFAULT '{}'
);

-- Data quality checks
CREATE TABLE pipeline_meta.data_quality_checks (
    check_id SERIAL PRIMARY KEY,
    pipeline_id INTEGER REFERENCES pipeline_meta.pipelines(pipeline_id),
    check_name VARCHAR(255) NOT NULL,
    check_type VARCHAR(100) NOT NULL, -- null_check, uniqueness, freshness, row_count, custom_sql
    check_sql TEXT,
    target_table VARCHAR(255),
    target_column VARCHAR(255),
    threshold_type VARCHAR(50), -- max_percent, min_count, max_age_hours
    threshold_value DECIMAL(10,4),
    is_active BOOLEAN DEFAULT true
);

-- Data quality results
CREATE TABLE pipeline_meta.quality_results (
    result_id SERIAL PRIMARY KEY,
    check_id INTEGER REFERENCES pipeline_meta.data_quality_checks(check_id),
    run_id INTEGER REFERENCES pipeline_meta.pipeline_runs(run_id),
    status VARCHAR(50) NOT NULL, -- pass, fail, warn, error
    actual_value DECIMAL(15,4),
    expected_value DECIMAL(15,4),
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details JSONB DEFAULT '{}'
);

-- Schema snapshots (for drift detection)
CREATE TABLE pipeline_meta.schema_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    table_name VARCHAR(255) NOT NULL,
    column_name VARCHAR(255) NOT NULL,
    data_type VARCHAR(100) NOT NULL,
    is_nullable BOOLEAN,
    ordinal_position INTEGER,
    snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent actions log
CREATE TABLE pipeline_meta.agent_actions (
    action_id SERIAL PRIMARY KEY,
    agent_name VARCHAR(100) NOT NULL, -- monitor, diagnostics, repair, orchestrator
    action_type VARCHAR(100) NOT NULL, -- alert, diagnosis, fix_proposed, fix_applied, escalation
    pipeline_id INTEGER REFERENCES pipeline_meta.pipelines(pipeline_id),
    run_id INTEGER REFERENCES pipeline_meta.pipeline_runs(run_id),
    summary TEXT,
    details JSONB DEFAULT '{}',
    confidence_score DECIMAL(3,2),
    status VARCHAR(50) DEFAULT 'pending', -- pending, approved, applied, rejected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- PART 4: Seed pipeline metadata
-- ============================================================

-- Define pipelines (matching dbt model flow)
INSERT INTO pipeline_meta.pipelines (pipeline_name, description, schedule, sla_minutes, owner) VALUES
('raw_customers_load',    'Load raw customer data from source',        '0 */6 * * *', 10, 'data-eng'),
('raw_orders_load',       'Load raw orders from source',               '0 */6 * * *', 15, 'data-eng'),
('raw_products_load',     'Load raw product catalog from source',      '0 0 * * *',   10, 'data-eng'),
('stg_customers',         'Stage and clean customer data',             '30 */6 * * *', 10, 'data-eng'),
('stg_orders',            'Stage and clean order data',                '30 */6 * * *', 15, 'data-eng'),
('stg_order_items',       'Stage and clean order items',               '30 */6 * * *', 10, 'data-eng'),
('stg_products',          'Stage and clean product data',              '15 0 * * *',   10, 'data-eng'),
('mart_customer_orders',  'Customer order summary mart',               '0 */6 * * *',  20, 'analytics'),
('mart_revenue_daily',    'Daily revenue aggregation',                 '0 1 * * *',    20, 'analytics'),
('mart_product_performance', 'Product performance metrics',            '0 1 * * *',    20, 'analytics');

-- Define dependencies (DAG)
INSERT INTO pipeline_meta.dependencies (pipeline_id, depends_on_pipeline_id) VALUES
(4, 1),   -- stg_customers depends on raw_customers_load
(5, 2),   -- stg_orders depends on raw_orders_load
(6, 2),   -- stg_order_items depends on raw_orders_load
(7, 3),   -- stg_products depends on raw_products_load
(8, 4),   -- mart_customer_orders depends on stg_customers
(8, 5),   -- mart_customer_orders depends on stg_orders
(9, 5),   -- mart_revenue_daily depends on stg_orders
(9, 6),   -- mart_revenue_daily depends on stg_order_items
(9, 7),   -- mart_revenue_daily depends on stg_products
(10, 6),  -- mart_product_performance depends on stg_order_items
(10, 7);  -- mart_product_performance depends on stg_products

-- Seed recent successful runs
INSERT INTO pipeline_meta.pipeline_runs (pipeline_id, status, started_at, completed_at, duration_seconds, row_count)
SELECT
    p.pipeline_id,
    'success',
    ts,
    ts + (p.sla_minutes * 0.5 * INTERVAL '1 minute'),
    (p.sla_minutes * 0.5 * 60)::int,
    (random() * 10000 + 100)::int
FROM pipeline_meta.pipelines p
CROSS JOIN generate_series(
    CURRENT_TIMESTAMP - INTERVAL '7 days',
    CURRENT_TIMESTAMP - INTERVAL '6 hours',
    INTERVAL '6 hours'
) AS ts
WHERE p.is_active = true;

-- Define data quality checks
INSERT INTO pipeline_meta.data_quality_checks (pipeline_id, check_name, check_type, target_table, target_column, threshold_type, threshold_value) VALUES
(4, 'customers_email_not_null',    'null_check',   'staging.stg_customers', 'email',        'max_percent', 0.0),
(4, 'customers_email_unique',      'uniqueness',   'staging.stg_customers', 'email',        'max_percent', 0.0),
(5, 'orders_amount_not_null',      'null_check',   'staging.stg_orders',    'total_amount', 'max_percent', 5.0),
(5, 'orders_row_count',            'row_count',    'staging.stg_orders',    NULL,           'min_count',   100.0),
(8, 'customer_orders_freshness',   'freshness',    'marts.mart_customer_orders', NULL,      'max_age_hours', 12.0),
(9, 'revenue_no_negatives',        'custom_sql',   'marts.mart_revenue_daily', 'total_revenue', 'max_percent', 0.0);

-- Take initial schema snapshot
INSERT INTO pipeline_meta.schema_snapshots (table_name, column_name, data_type, is_nullable, ordinal_position)
SELECT
    table_schema || '.' || table_name,
    column_name,
    data_type,
    is_nullable = 'YES',
    ordinal_position
FROM information_schema.columns
WHERE table_schema IN ('raw', 'staging', 'marts')
ORDER BY table_schema, table_name, ordinal_position;

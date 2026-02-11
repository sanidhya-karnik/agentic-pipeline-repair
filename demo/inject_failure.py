"""
Demo Scenario Injector: Simulates pipeline failures for demonstration.

Usage:
    python -m demo.inject_failure --scenario schema_drift
    python -m demo.inject_failure --scenario data_quality
    python -m demo.inject_failure --scenario sla_breach
    python -m demo.inject_failure --scenario all
"""

import argparse
import json
import os
from datetime import datetime, timedelta
from src.config.db import execute_query, execute_write


def inject_schema_drift():
    """Scenario 1: Add an unexpected column to raw.orders, simulating upstream schema change."""
    print("[INJECT] Schema drift: Adding 'discount_amount' column to raw.orders...")

    # Add new column
    execute_write("""
        ALTER TABLE raw.orders ADD COLUMN IF NOT EXISTS discount_amount DECIMAL(10,2) DEFAULT 0.00;
    """)

    # Populate with some data
    execute_write("""
        UPDATE raw.orders SET discount_amount = CASE
            WHEN random() > 0.7 THEN (total_amount * random() * 0.2)::decimal(10,2)
            ELSE 0.00
        END;
    """)

    # Log a failed pipeline run for stg_orders
    execute_write("""
        INSERT INTO pipeline_meta.pipeline_runs
            (pipeline_id, status, started_at, completed_at, duration_seconds, error_message)
        VALUES (
            (SELECT pipeline_id FROM pipeline_meta.pipelines WHERE pipeline_name = 'stg_orders'),
            'failed',
            NOW() - INTERVAL '30 minutes',
            NOW() - INTERVAL '28 minutes',
            120,
            'Compilation Error in model stg_orders: column "discount_amount" referenced in downstream mart_revenue_daily does not exist in stg_orders output.'
        );
    """)

    # Also fail downstream
    execute_write("""
        INSERT INTO pipeline_meta.pipeline_runs
            (pipeline_id, status, started_at, completed_at, duration_seconds, error_message)
        VALUES (
            (SELECT pipeline_id FROM pipeline_meta.pipelines WHERE pipeline_name = 'mart_revenue_daily'),
            'failed',
            NOW() - INTERVAL '25 minutes',
            NOW() - INTERVAL '24 minutes',
            60,
            'Database Error: column "discount_amount" does not exist. Upstream dependency stg_orders may have schema changes.'
        );
    """)

    print("   Done. raw.orders now has 'discount_amount' column.")
    print("   Done. stg_orders and mart_revenue_daily marked as FAILED.")


def inject_data_quality_issue():
    """Scenario 2: Inject nulls into critical fields."""
    print("[INJECT] Data quality issue: Setting NULL total_amount on recent orders...")

    # Null out some order amounts
    execute_write("""
        UPDATE raw.orders
        SET total_amount = NULL
        WHERE order_id IN (
            SELECT order_id FROM raw.orders
            ORDER BY order_date DESC
            LIMIT 75
        );
    """)

    # Log quality check failure
    execute_write("""
        INSERT INTO pipeline_meta.pipeline_runs
            (pipeline_id, status, started_at, completed_at, duration_seconds, row_count)
        VALUES (
            (SELECT pipeline_id FROM pipeline_meta.pipelines WHERE pipeline_name = 'stg_orders'),
            'success',
            NOW() - INTERVAL '15 minutes',
            NOW() - INTERVAL '12 minutes',
            180,
            500
        );
    """)

    # Record quality check failure
    execute_write("""
        INSERT INTO pipeline_meta.quality_results
            (check_id, run_id, status, actual_value, expected_value, details)
        VALUES (
            (SELECT check_id FROM pipeline_meta.data_quality_checks WHERE check_name = 'orders_amount_not_null'),
            (SELECT MAX(run_id) FROM pipeline_meta.pipeline_runs),
            'fail',
            15.0,
            5.0,
            '{"null_count": 75, "total_rows": 500, "null_percent": 15.0, "threshold": 5.0}'::jsonb
        );
    """)

    print("   Done. 75 orders now have NULL total_amount (15% null rate, threshold is 5%).")
    print("   Done. Data quality check recorded as FAILED.")


def inject_sla_breach():
    """Scenario 3: Simulate a pipeline running way over SLA."""
    print("[INJECT] SLA breach: mart_customer_orders running 3x over SLA...")

    execute_write("""
        INSERT INTO pipeline_meta.pipeline_runs
            (pipeline_id, status, started_at, completed_at, duration_seconds, row_count)
        VALUES (
            (SELECT pipeline_id FROM pipeline_meta.pipelines WHERE pipeline_name = 'mart_customer_orders'),
            'running',
            NOW() - INTERVAL '65 minutes',
            NULL,
            3900,
            NULL
        );
    """)

    print("   Done. mart_customer_orders has been 'running' for 65 min (SLA: 20 min).")


def reset_demo():
    """Reset all injected failures back to clean state."""
    print("[RESET] Resetting demo state...")

    # Remove added column
    execute_write("ALTER TABLE raw.orders DROP COLUMN IF EXISTS discount_amount CASCADE;")

    # Restore null amounts
    execute_write("""
        UPDATE raw.orders SET total_amount = (random() * 500 + 20)::decimal(10,2)
        WHERE total_amount IS NULL;
    """)

    # Remove failed/running runs from last hour
    execute_write("""
        DELETE FROM pipeline_meta.pipeline_runs
        WHERE started_at > NOW() - INTERVAL '2 hours'
        AND status IN ('failed', 'running');
    """)

    # Clear all quality results and seed passing ones
    execute_write("DELETE FROM pipeline_meta.quality_results;")
    
    # Seed passing quality check results so "check" shows all green
    # Actual values must be BELOW thresholds for max checks, ABOVE for min checks
    execute_write("""
        INSERT INTO pipeline_meta.quality_results (check_id, status, actual_value, expected_value, checked_at, details)
        SELECT 
            check_id,
            'pass',
            CASE 
                WHEN threshold_type = 'max_percent' THEN GREATEST(0, threshold_value - 1.0)
                WHEN threshold_type = 'min_count' THEN threshold_value + 100
                WHEN threshold_type = 'max_age_hours' THEN GREATEST(0.5, threshold_value - 2.0)
                WHEN threshold_type = 'max_count' THEN GREATEST(0, threshold_value - 1)
                ELSE 0
            END,
            threshold_value,
            NOW() - INTERVAL '30 minutes',
            '{"status": "healthy"}'::jsonb
        FROM pipeline_meta.data_quality_checks
        WHERE is_active = true;
    """)

    # Clear agent actions
    execute_write("DELETE FROM pipeline_meta.agent_actions;")

    # Re-snapshot schema
    execute_write("DELETE FROM pipeline_meta.schema_snapshots;")
    execute_write("""
        INSERT INTO pipeline_meta.schema_snapshots (table_name, column_name, data_type, is_nullable, ordinal_position)
        SELECT
            table_schema || '.' || table_name,
            column_name, data_type, is_nullable = 'YES', ordinal_position
        FROM information_schema.columns
        WHERE table_schema IN ('raw', 'staging', 'marts')
        ORDER BY table_schema, table_name, ordinal_position;
    """)

    # Restore dbt model from backup if it exists
    import glob
    for backup in glob.glob(os.path.join(os.path.dirname(os.path.dirname(__file__)), "dbt_project", "models", "**", "*.sql.backup"), recursive=True):
        original = backup.replace(".backup", "")
        with open(backup, "r") as f:
            content = f.read()
        with open(original, "w") as f:
            f.write(content)
        os.remove(backup)
        print(f"   Restored {os.path.basename(original)} from backup.")

    # Re-run dbt to recreate views that may have been dropped by CASCADE
    import subprocess
    dbt_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dbt_project")
    subprocess.run(
        ["dbt", "run", "--profiles-dir", "."],
        cwd=dbt_dir, capture_output=True, text=True,
        env={**os.environ},
    )
    print("   dbt models rebuilt.")

    print("   Done. Demo state reset to clean.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inject demo failures into the pipeline")
    parser.add_argument(
        "--scenario",
        choices=["schema_drift", "data_quality", "sla_breach", "all", "reset"],
        required=True,
        help="Which failure scenario to inject",
    )
    args = parser.parse_args()

    if args.scenario == "schema_drift":
        inject_schema_drift()
    elif args.scenario == "data_quality":
        inject_data_quality_issue()
    elif args.scenario == "sla_breach":
        inject_sla_breach()
    elif args.scenario == "all":
        inject_schema_drift()
        inject_data_quality_issue()
        inject_sla_breach()
    elif args.scenario == "reset":
        reset_demo()

    print("\nDone! Run the orchestrator to see the agents respond:")
    print("  python -m src.agents.orchestrator")

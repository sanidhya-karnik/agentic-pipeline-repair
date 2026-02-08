"""
MCP Server exposing pipeline metadata tools for agents.

Tools:
- get_pipeline_status: Current state of all pipelines
- get_pipeline_dag: Dependency graph for a pipeline
- get_run_history: Recent run history for a pipeline
- get_schema_info: Table schemas and column stats
- get_quality_checks: Data quality check results
- list_dbt_models: Discover all dbt models
- get_dbt_model_sql: Read dbt model SQL source code
- get_monitored_tables: Discover tables tracked for schema drift
- get_pipelines_with_quality_checks: Discover pipelines with quality checks
- execute_diagnostic_sql: Run read-only diagnostic queries
- log_agent_action: Record an agent action
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any
from strands import tool
from src.config.db import execute_query, execute_write

DBT_PROJECT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dbt_project")


@tool
def get_pipeline_status() -> str:
    """Get the current status of all pipelines including last run info and SLA status.
    Returns a summary of each pipeline with its latest run status, duration, and whether it met SLA."""
    sql = """
        SELECT
            p.pipeline_id,
            p.pipeline_name,
            p.schedule,
            p.sla_minutes,
            p.owner,
            lr.status AS last_run_status,
            lr.started_at AS last_run_started,
            lr.duration_seconds AS last_run_duration_sec,
            lr.row_count AS last_run_rows,
            lr.error_message,
            CASE
                WHEN lr.duration_seconds > p.sla_minutes * 60 THEN 'SLA_BREACHED'
                WHEN lr.status = 'failed' THEN 'FAILED'
                WHEN lr.status = 'running' THEN 'RUNNING'
                ELSE 'HEALTHY'
            END AS health_status
        FROM pipeline_meta.pipelines p
        LEFT JOIN LATERAL (
            SELECT * FROM pipeline_meta.pipeline_runs pr
            WHERE pr.pipeline_id = p.pipeline_id
            ORDER BY pr.started_at DESC
            LIMIT 1
        ) lr ON true
        WHERE p.is_active = true
        ORDER BY
            CASE
                WHEN lr.status = 'failed' THEN 0
                WHEN lr.duration_seconds > p.sla_minutes * 60 THEN 1
                ELSE 2
            END,
            p.pipeline_name;
    """
    results = execute_query(sql)
    return json.dumps(results, default=str, indent=2)


@tool
def get_pipeline_dag(pipeline_name: str) -> str:
    """Get the dependency graph (upstream and downstream) for a given pipeline.
    Shows what pipelines this one depends on and what depends on it.

    Args:
        pipeline_name: Name of the pipeline to get dependencies for.
    """
    sql = """
        WITH target AS (
            SELECT pipeline_id FROM pipeline_meta.pipelines WHERE pipeline_name = %s
        ),
        upstream AS (
            SELECT p.pipeline_name, 'upstream' AS direction
            FROM pipeline_meta.dependencies d
            JOIN pipeline_meta.pipelines p ON p.pipeline_id = d.depends_on_pipeline_id
            WHERE d.pipeline_id = (SELECT pipeline_id FROM target)
        ),
        downstream AS (
            SELECT p.pipeline_name, 'downstream' AS direction
            FROM pipeline_meta.dependencies d
            JOIN pipeline_meta.pipelines p ON p.pipeline_id = d.pipeline_id
            WHERE d.depends_on_pipeline_id = (SELECT pipeline_id FROM target)
        )
        SELECT * FROM upstream
        UNION ALL
        SELECT %s, 'target'
        UNION ALL
        SELECT * FROM downstream;
    """
    results = execute_query(sql, (pipeline_name, pipeline_name))
    return json.dumps(results, default=str, indent=2)


@tool
def get_run_history(pipeline_name: str, limit: int = 10) -> str:
    """Get recent run history for a pipeline including status, duration, row counts, and errors.

    Args:
        pipeline_name: Name of the pipeline.
        limit: Number of recent runs to return (default 10).
    """
    sql = """
        SELECT
            pr.run_id,
            pr.status,
            pr.started_at,
            pr.completed_at,
            pr.duration_seconds,
            pr.row_count,
            pr.error_message,
            pr.run_metadata
        FROM pipeline_meta.pipeline_runs pr
        JOIN pipeline_meta.pipelines p ON p.pipeline_id = pr.pipeline_id
        WHERE p.pipeline_name = %s
        ORDER BY pr.started_at DESC
        LIMIT %s;
    """
    results = execute_query(sql, (pipeline_name, limit))
    return json.dumps(results, default=str, indent=2)


@tool
def get_schema_info(table_name: str) -> str:
    """Get the current schema for a table and compare with the last snapshot to detect drift.
    Returns column names, types, and any differences from the last recorded snapshot.

    Args:
        table_name: Fully qualified table name (e.g., 'raw.customers').
    """
    parts = table_name.split(".")
    if len(parts) != 2:
        return json.dumps({"error": "Table name must be schema.table format (e.g., 'raw.customers')"})

    schema_name, tbl_name = parts

    # Current schema from information_schema
    current_sql = """
        SELECT column_name, data_type, is_nullable, ordinal_position
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position;
    """
    current = execute_query(current_sql, (schema_name, tbl_name))

    # Last snapshot
    snapshot_sql = """
        SELECT column_name, data_type, is_nullable, ordinal_position
        FROM pipeline_meta.schema_snapshots
        WHERE table_name = %s
        ORDER BY ordinal_position;
    """
    snapshot = execute_query(snapshot_sql, (table_name,))

    # Detect drift
    current_cols = {c["column_name"] for c in current}
    snapshot_cols = {c["column_name"] for c in snapshot}
    added = current_cols - snapshot_cols
    removed = snapshot_cols - current_cols

    result = {
        "table": table_name,
        "current_columns": current,
        "snapshot_columns": snapshot,
        "drift_detected": bool(added or removed),
        "columns_added": list(added),
        "columns_removed": list(removed),
    }
    return json.dumps(result, default=str, indent=2)


@tool
def get_quality_checks(pipeline_name: str) -> str:
    """Get data quality check definitions and their most recent results for a pipeline.

    Args:
        pipeline_name: Name of the pipeline.
    """
    sql = """
        SELECT
            dqc.check_id,
            dqc.check_name,
            dqc.check_type,
            dqc.target_table,
            dqc.target_column,
            dqc.threshold_type,
            dqc.threshold_value,
            qr.status AS last_result_status,
            qr.actual_value,
            qr.expected_value,
            qr.checked_at,
            qr.details
        FROM pipeline_meta.data_quality_checks dqc
        JOIN pipeline_meta.pipelines p ON p.pipeline_id = dqc.pipeline_id
        LEFT JOIN LATERAL (
            SELECT * FROM pipeline_meta.quality_results qr2
            WHERE qr2.check_id = dqc.check_id
            ORDER BY qr2.checked_at DESC
            LIMIT 1
        ) qr ON true
        WHERE p.pipeline_name = %s AND dqc.is_active = true;
    """
    results = execute_query(sql, (pipeline_name,))
    return json.dumps(results, default=str, indent=2)


@tool
def execute_diagnostic_sql(sql_query: str) -> str:
    """Execute a READ-ONLY SQL query for diagnostic purposes.
    Only SELECT statements are allowed. Use this to investigate data issues,
    check row counts, find null values, or run ad-hoc analysis.

    Args:
        sql_query: A SELECT SQL query to execute (no INSERT/UPDATE/DELETE).
    """
    # Safety: only allow SELECT
    normalized = sql_query.strip().upper()
    if not normalized.startswith("SELECT") and not normalized.startswith("WITH"):
        return json.dumps({"error": "Only SELECT/WITH queries allowed for diagnostics."})

    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]
    for word in forbidden:
        if word in normalized:
            return json.dumps({"error": f"Forbidden keyword detected: {word}"})

    try:
        results = execute_query(sql_query, read_only=True)
        # Limit result size
        if len(results) > 100:
            results = results[:100]
            return json.dumps({"data": results, "note": "Results truncated to 100 rows"}, default=str, indent=2)
        return json.dumps({"data": results, "row_count": len(results)}, default=str, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def log_agent_action(
    agent_name: str,
    action_type: str,
    pipeline_name: str,
    summary: str,
    details: str = "{}",
    confidence_score: float = 0.0,
) -> str:
    """Log an action taken by an agent for audit trail and dashboard display.

    Args:
        agent_name: Which agent is acting (monitor, diagnostics, repair, orchestrator).
        action_type: Type of action (alert, diagnosis, fix_proposed, fix_applied, escalation).
        pipeline_name: Name of the affected pipeline.
        summary: Brief human-readable summary of the action.
        details: JSON string with detailed information.
        confidence_score: Agent's confidence in this action (0.0 to 1.0).
    """
    sql = """
        INSERT INTO pipeline_meta.agent_actions
            (agent_name, action_type, pipeline_id, summary, details, confidence_score)
        VALUES (
            %s, %s,
            (SELECT pipeline_id FROM pipeline_meta.pipelines WHERE pipeline_name = %s),
            %s, %s::jsonb, %s
        )
        RETURNING action_id, created_at;
    """
    try:
        result = execute_query(
            sql,
            (agent_name, action_type, pipeline_name, summary, details, confidence_score),
            read_only=False,
        )
        return json.dumps({"logged": True, "action": result[0] if result else {}}, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def list_dbt_models() -> str:
    """List all available dbt models with their file paths and categories (staging/marts).
    Use this to discover what dbt models exist in the project."""
    models = []
    models_dir = os.path.join(DBT_PROJECT_PATH, "models")
    if not os.path.exists(models_dir):
        return json.dumps({"error": f"dbt models directory not found at {models_dir}"})

    for root, dirs, files in os.walk(models_dir):
        for f in files:
            if f.endswith(".sql"):
                rel_path = os.path.relpath(os.path.join(root, f), DBT_PROJECT_PATH)
                category = os.path.basename(root)
                models.append({
                    "model_name": f.replace(".sql", ""),
                    "category": category,
                    "path": rel_path,
                })
    return json.dumps(models, indent=2)


@tool
def get_dbt_model_sql(model_name: str) -> str:
    """Read the SQL source code of a dbt model. Returns the full SQL including
    Jinja references like {{ source() }} and {{ ref() }}.
    Use this to understand what a pipeline transformation does and to propose fixes.

    Args:
        model_name: Name of the dbt model (e.g., 'stg_orders', 'mart_revenue_daily').
    """
    models_dir = os.path.join(DBT_PROJECT_PATH, "models")
    if not os.path.exists(models_dir):
        return json.dumps({"error": "dbt models directory not found"})

    for root, dirs, files in os.walk(models_dir):
        for f in files:
            if f == f"{model_name}.sql":
                filepath = os.path.join(root, f)
                with open(filepath, "r") as fh:
                    sql_content = fh.read()
                return json.dumps({
                    "model_name": model_name,
                    "path": os.path.relpath(filepath, DBT_PROJECT_PATH),
                    "sql": sql_content,
                }, indent=2)

    return json.dumps({"error": f"Model '{model_name}' not found in dbt project"})


@tool
def get_monitored_tables() -> str:
    """Get all tables that have schema snapshots for drift monitoring.
    Returns the list of tables being tracked for schema changes."""
    sql = """
        SELECT DISTINCT table_name
        FROM pipeline_meta.schema_snapshots
        ORDER BY table_name;
    """
    results = execute_query(sql)
    return json.dumps([r["table_name"] for r in results], indent=2)


@tool
def get_pipelines_with_quality_checks() -> str:
    """Get all pipelines that have data quality checks defined.
    Returns pipeline names and their check counts."""
    sql = """
        SELECT
            p.pipeline_name,
            COUNT(dqc.check_id) AS check_count
        FROM pipeline_meta.data_quality_checks dqc
        JOIN pipeline_meta.pipelines p ON p.pipeline_id = dqc.pipeline_id
        WHERE dqc.is_active = true
        GROUP BY p.pipeline_name
        ORDER BY p.pipeline_name;
    """
    results = execute_query(sql)
    return json.dumps(results, default=str, indent=2)


# Collect all tools for agent use
ALL_TOOLS = [
    get_pipeline_status,
    get_pipeline_dag,
    get_run_history,
    get_schema_info,
    get_quality_checks,
    execute_diagnostic_sql,
    log_agent_action,
    list_dbt_models,
    get_dbt_model_sql,
    get_monitored_tables,
    get_pipelines_with_quality_checks,
]

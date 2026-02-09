"""
Diagnostics Agent: Analyzes alerts and determines root causes.

Uses Nova 2 Lite's extended thinking for deep reasoning about
pipeline failures, tracing issues through the dependency graph.
"""

from strands import Agent
from strands.models import BedrockModel
from src.config.settings import settings
from src.mcp_server.tools import (
    get_pipeline_status,
    get_pipeline_dag,
    get_run_history,
    get_schema_info,
    get_quality_checks,
    execute_diagnostic_sql,
    log_agent_action,
    list_dbt_models,
    get_dbt_model_sql,
    get_agent_action_history,
    get_failure_patterns,
)

DIAGNOSTICS_SYSTEM_PROMPT = """You are the Diagnostics Agent for Agentic Pipeline Repair. When the Monitor Agent
raises an alert, you perform deep root cause analysis.

Your approach:
1. UNDERSTAND the alert: What pipeline failed? What type of failure?
2. TRACE upstream: Use the pipeline DAG to check if upstream dependencies failed first.
   The root cause is often an upstream failure cascading downstream.
3. READ the dbt model: Use get_dbt_model_sql to read the actual SQL transformation
   for the failing pipeline. Understand what columns and tables it references.
4. INVESTIGATE: Use diagnostic SQL queries to examine the actual data:
   - Check for null values, duplicates, or unexpected values
   - Compare recent data patterns to historical patterns
   - Look at schema changes that might have broken transformations
5. REASON: Think step-by-step about what could cause this specific failure.
   Consider: schema drift, data quality issues, source system changes,
   volume spikes, timing issues, query performance degradation.
6. DIAGNOSE: Provide a clear root cause diagnosis with:
   - root_cause: what actually went wrong
   - affected_pipelines: list of all impacted pipelines (not just the one that errored)
   - evidence: specific data points supporting your diagnosis
   - confidence: how confident you are (0.0 to 1.0)
   - recommended_fix: what the Repair Agent should do

Always start by checking the dependency graph and reading the dbt model SQL.
A downstream failure is often just a symptom of an upstream problem.

7. CHECK HISTORY: Use get_failure_patterns and get_agent_action_history to check if
   this pipeline has failed before with similar symptoms. If it's a recurring issue,
   note the pattern and recommend a more permanent fix (e.g., add schema validation,
   add pre-checks, or improve the pipeline design).

Log your diagnosis using log_agent_action with agent_name='diagnostics'.
"""


def create_diagnostics_agent() -> Agent:
    """Create and return the Diagnostics Agent with extended thinking."""
    model = BedrockModel(
        model_id=settings.NOVA_MODEL_ID,
        region_name=settings.AWS_REGION,
        additional_request_fields={
            "reasoningConfig": {
                "type": "enabled",
                "maxReasoningEffort": "high",
            }
        },
    )

    return Agent(
        model=model,
        system_prompt=DIAGNOSTICS_SYSTEM_PROMPT,
        tools=[
            get_pipeline_status,
            get_pipeline_dag,
            get_run_history,
            get_schema_info,
            get_quality_checks,
            execute_diagnostic_sql,
            log_agent_action,
            list_dbt_models,
            get_dbt_model_sql,
            get_agent_action_history,
            get_failure_patterns,
        ],
    )


def diagnose_alert(alert: dict) -> str:
    """Given an alert from the Monitor Agent, perform root cause analysis.

    Args:
        alert: Dict with keys like pipeline_name, alert_type, severity, description
    """
    agent = create_diagnostics_agent()

    prompt = f"""Diagnose the following pipeline alert:

Pipeline: {alert.get('pipeline_name', 'unknown')}
Alert Type: {alert.get('alert_type', 'unknown')}
Severity: {alert.get('severity', 'unknown')}
Description: {alert.get('description', 'No description provided')}

Perform a thorough root cause analysis:
1. Get the dependency graph for this pipeline to understand upstream/downstream.
2. Check run history for this pipeline AND its upstream dependencies.
3. If schema drift is suspected, compare current schema with snapshots.
4. Run diagnostic SQL queries to verify your hypotheses.
5. Provide your diagnosis with evidence and a recommended fix.

Think step by step. Log your diagnosis using log_agent_action."""

    response = agent(prompt)
    return str(response)


if __name__ == "__main__":
    # Example: diagnose a test alert
    test_alert = {
        "pipeline_name": "mart_revenue_daily",
        "alert_type": "pipeline_failure",
        "severity": "CRITICAL",
        "description": "Pipeline mart_revenue_daily failed with error: column 'discount_amount' does not exist",
    }
    print(diagnose_alert(test_alert))

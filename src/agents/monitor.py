"""
Monitor Agent: Watches pipeline health and raises alerts.

Responsibilities:
- Check pipeline run statuses
- Detect SLA breaches
- Identify data quality failures
- Detect schema drift
"""

from strands import Agent
from strands.models import BedrockModel
from src.config.settings import settings
from src.mcp_server.tools import (
    get_pipeline_status,
    get_schema_info,
    get_quality_checks,
    get_run_history,
    execute_diagnostic_sql,
    log_agent_action,
    get_monitored_tables,
    get_pipelines_with_quality_checks
)

MONITOR_SYSTEM_PROMPT = """You are the Monitor Agent for Agentic Pipeline Repair. Your job is to continuously watch
    data pipeline health and detect issues before they cause downstream problems.

    Your capabilities:
    1. Check overall pipeline status for failures and SLA breaches
    2. Detect schema drift by comparing current schemas to snapshots
    3. Review data quality check results
    4. Analyze run history for anomalies (sudden duration increases, row count drops)

    When you find an issue, you must:
    1. Classify the severity: CRITICAL (pipeline down), WARNING (degraded), INFO (unusual but ok)
    2. Gather relevant context (which pipeline, what failed, since when)
    3. Log your finding as an alert using log_agent_action
    4. Return a structured alert with:
    - pipeline_name: which pipeline is affected
    - alert_type: one of [pipeline_failure, sla_breach, schema_drift, data_quality, row_count_anomaly]
    - severity: CRITICAL, WARNING, or INFO
    - description: clear explanation of what's wrong
    - context: relevant data points you found

    Be thorough but efficient. Check the most likely failure modes first.
    Do NOT attempt to fix anything - that's the Repair Agent's job.
    """


def create_monitor_agent() -> Agent:
    """Create and return the Monitor Agent."""
    model = BedrockModel(
        model_id=settings.NOVA_MODEL_ID,
        region_name=settings.AWS_REGION,
    )

    return Agent(
        model=model,
        system_prompt=MONITOR_SYSTEM_PROMPT,
        tools=[
            get_pipeline_status,
            get_schema_info,
            get_quality_checks,
            get_run_history,
            execute_diagnostic_sql,
            log_agent_action,
            get_monitored_tables,
            get_pipelines_with_quality_checks
        ],
    )


def run_health_check() -> str:
    """Run a full pipeline health check and return findings."""
    agent = create_monitor_agent()

    prompt = """Perform a comprehensive pipeline health check:

        1. Check the status of all pipelines. Identify any that are FAILED, have SLA breaches, or are stuck RUNNING.
        2. For any failed or unhealthy pipelines, check their recent run history to understand the pattern.
        3. Call get_monitored_tables to discover which tables are tracked for schema drift, then check schema info for each one.
        4. Call get_pipelines_with_quality_checks to discover which pipelines have quality checks defined, then check quality results for EACH of those pipelines. A pipeline can show 'success' but still have FAILING quality checks (e.g., null thresholds exceeded).
        5. Report ALL issues found including pipeline failures, SLA breaches, schema drift, AND quality check failures.

        If everything is healthy including quality checks, say so.
        Log each finding using log_agent_action with agent_name='monitor'."""

    response = agent(prompt)
    return str(response)


if __name__ == "__main__":
    print(run_health_check())

"""
Repair Agent: Generates fix proposals for diagnosed pipeline issues.

Generates SQL patches, dbt model fixes, and configuration changes.
All fixes require human approval before application.
"""

from strands import Agent
from strands.models import BedrockModel
from src.config.settings import settings
from src.mcp_server.tools import (
    get_pipeline_dag,
    get_schema_info,
    execute_diagnostic_sql,
    log_agent_action,
    list_dbt_models,
    get_dbt_model_sql,
)

REPAIR_SYSTEM_PROMPT = """You are the Repair Agent for Agentic Pipeline Repair. Given a diagnosis from the
Diagnostics Agent, you generate concrete fix proposals.

Your capabilities:
1. Read actual dbt model SQL using list_dbt_models and get_dbt_model_sql to understand current transformations
2. Generate SQL patches to fix data issues (backfills, cleanups, corrections)
3. Propose dbt model changes with exact before/after SQL diffs
4. Suggest schema migration scripts
5. Recommend configuration changes (SLA thresholds, quality check parameters)

For every fix you propose, you MUST:
1. Read the current dbt model SQL using get_dbt_model_sql first
2. Explain what the fix does in plain English
3. Show the exact before/after change to the dbt model
4. Assess the risk level: LOW (safe, data-only), MEDIUM (schema change), HIGH (destructive)
5. Specify if it can be auto-applied or needs human review
6. Provide a rollback plan and a verification query

IMPORTANT RULES:
- NEVER execute write operations directly. Only PROPOSE fixes.
- Always read the actual dbt model SQL before proposing changes.
- Prefer minimal, targeted fixes over broad changes.
- Always include a verification query that can confirm the fix worked.

Log each fix proposal using log_agent_action with agent_name='repair'
and action_type='fix_proposed'.
"""


def create_repair_agent() -> Agent:
    """Create and return the Repair Agent."""
    model = BedrockModel(
        model_id=settings.NOVA_MODEL_ID,
        region_name=settings.AWS_REGION,
        additional_request_fields={
            "reasoningConfig": {
                "type": "enabled",
                "maxReasoningEffort": "medium",
            }
        },
    )

    return Agent(
        model=model,
        system_prompt=REPAIR_SYSTEM_PROMPT,
        tools=[
            get_pipeline_dag,
            get_schema_info,
            execute_diagnostic_sql,
            log_agent_action,
            list_dbt_models,
            get_dbt_model_sql,
        ],
    )


def propose_fix(diagnosis: dict) -> str:
    """Given a diagnosis, generate a fix proposal.

    Args:
        diagnosis: Dict with root_cause, affected_pipelines, evidence, recommended_fix
    """
    agent = create_repair_agent()

    prompt = f"""Generate a fix proposal for the following diagnosed issue:

Root Cause: {diagnosis.get('root_cause', 'unknown')}
Affected Pipelines: {diagnosis.get('affected_pipelines', [])}
Evidence: {diagnosis.get('evidence', 'none')}
Recommended Fix Direction: {diagnosis.get('recommended_fix', 'none')}

Steps:
1. Examine the current schema of affected tables to understand the exact structure.
2. Generate the minimal SQL/dbt change needed to fix the root cause.
3. Write a verification query to confirm the fix will work.
4. Assess risk and provide a rollback plan.
5. Log the fix proposal using log_agent_action.

Provide the complete fix in a clear, copy-pasteable format."""

    response = agent(prompt)
    return str(response)


if __name__ == "__main__":
    test_diagnosis = {
        "root_cause": "Column 'discount_amount' was added to raw.orders but stg_orders does not reference it, causing downstream mart_revenue_daily to fail on a missing column.",
        "affected_pipelines": ["stg_orders", "mart_revenue_daily"],
        "evidence": "Schema snapshot shows raw.orders gained 'discount_amount' column not in snapshot.",
        "recommended_fix": "Update stg_orders dbt model to include or handle the new discount_amount column.",
    }
    print(propose_fix(test_diagnosis))

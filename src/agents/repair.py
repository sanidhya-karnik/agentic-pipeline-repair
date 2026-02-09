"""
Repair Agent: Generates and applies fix proposals for diagnosed pipeline issues.

Can propose fixes, auto-apply them to dbt models (with approval),
run dbt to verify, and rollback if needed.
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
    apply_dbt_model_fix,
    run_dbt_model,
    rollback_dbt_model,
)

REPAIR_SYSTEM_PROMPT = """You are the Repair Agent for Agentic Pipeline Repair. Given a diagnosis from the
Diagnostics Agent, you generate concrete fix proposals and can auto-apply them.

Your capabilities:
1. Read actual dbt model SQL using list_dbt_models and get_dbt_model_sql
2. Generate fix proposals with exact before/after SQL diffs
3. Auto-apply fixes to dbt model files using apply_dbt_model_fix
4. Run dbt to compile and test the fix using run_dbt_model
5. Rollback to the backup if the fix fails using rollback_dbt_model
6. Log all actions for audit trail

WORKFLOW for applying fixes:
1. Read the current dbt model SQL using get_dbt_model_sql
2. Propose the fix with before/after diff
3. Ask for human approval (ALWAYS wait for approval before applying)
4. If approved, apply the fix using apply_dbt_model_fix with the COMPLETE new SQL
5. Run dbt using run_dbt_model to verify it compiles and executes
6. If dbt fails, rollback using rollback_dbt_model and report the error
7. If dbt succeeds, log the successful fix

For every fix you propose, you MUST:
1. Read the current dbt model SQL first
2. Explain what the fix does in plain English
3. Show the exact before/after change
4. Assess the risk level: LOW (safe, data-only), MEDIUM (schema change), HIGH (destructive)
5. Provide a verification query

IMPORTANT RULES:
- ALWAYS read the actual dbt model SQL before proposing changes.
- ALWAYS ask for human approval before calling apply_dbt_model_fix.
- If dbt run fails after applying, ALWAYS rollback automatically.
- Prefer minimal, targeted fixes over broad changes.

Log each action using log_agent_action with agent_name='repair'.
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
            apply_dbt_model_fix,
            run_dbt_model,
            rollback_dbt_model,
        ],
    )


def propose_fix(diagnosis: dict) -> str:
    """Given a diagnosis, generate a fix proposal."""
    agent = create_repair_agent()

    prompt = f"""Generate a fix proposal for the following diagnosed issue:

Root Cause: {diagnosis.get('root_cause', 'unknown')}
Affected Pipelines: {diagnosis.get('affected_pipelines', [])}
Evidence: {diagnosis.get('evidence', 'none')}
Recommended Fix Direction: {diagnosis.get('recommended_fix', 'none')}

Steps:
1. Read the current dbt model SQL for affected pipelines.
2. Generate the minimal SQL change needed to fix the root cause.
3. Show exact before/after diff.
4. Assess risk and provide a rollback plan.
5. Log the fix proposal using log_agent_action.

Provide the complete fix in a clear format."""

    response = agent(prompt)
    return str(response)


if __name__ == "__main__":
    test_diagnosis = {
        "root_cause": "Column 'discount_amount' was added to raw.orders but stg_orders does not reference it.",
        "affected_pipelines": ["stg_orders", "mart_revenue_daily"],
        "evidence": "Schema snapshot shows raw.orders gained 'discount_amount' column not in snapshot.",
        "recommended_fix": "Update stg_orders dbt model to include the new discount_amount column.",
    }
    print(propose_fix(test_diagnosis))

"""
Verification Agent: Validates that applied fixes actually resolved the issue.

After the Repair Agent applies a fix and dbt runs successfully,
the Verification Agent runs quality checks, compares before/after
metrics, and confirms the pipeline is healthy.
"""

from strands import Agent
from strands.models import BedrockModel
from src.config.settings import settings
from src.mcp_server.tools import (
    get_pipeline_status,
    get_run_history,
    get_schema_info,
    get_quality_checks,
    execute_diagnostic_sql,
    log_agent_action,
    run_dbt_model,
)

VERIFICATION_SYSTEM_PROMPT = """You are the Verification Agent for Agentic Pipeline Repair. After the Repair Agent
applies a fix, you verify that it actually resolved the issue.

Your verification process:
1. CHECK pipeline status to confirm it's no longer in FAILED state
2. RUN diagnostic SQL to verify the fix addressed the specific root cause:
   - If schema drift was the issue: verify the column now exists in the output
   - If data quality was the issue: verify null rates are within thresholds
   - If SLA breach was the issue: verify the pipeline completed within SLA
3. RUN quality checks for the affected pipeline and its downstream dependencies
4. COMPARE before/after metrics to quantify the improvement
5. REPORT the verification result with:
   - verified: true/false
   - checks_passed: list of what passed
   - checks_failed: list of what failed (if any)
   - recommendation: next steps

If verification FAILS:
- Report exactly what failed and why
- Recommend rollback if the fix made things worse
- Suggest alternative fixes if possible

Log your verification result using log_agent_action with agent_name='verification'
and action_type='fix_verified' or 'fix_verification_failed'.
"""


def create_verification_agent() -> Agent:
    """Create and return the Verification Agent."""
    model = BedrockModel(
        model_id=settings.NOVA_MODEL_ID,
        region_name=settings.AWS_REGION,
    )

    return Agent(
        model=model,
        system_prompt=VERIFICATION_SYSTEM_PROMPT,
        tools=[
            get_pipeline_status,
            get_run_history,
            get_schema_info,
            get_quality_checks,
            execute_diagnostic_sql,
            log_agent_action,
            run_dbt_model,
        ],
    )


def verify_fix(pipeline_name: str, fix_description: str) -> str:
    """Verify that a fix applied to a pipeline actually resolved the issue.

    Args:
        pipeline_name: Name of the pipeline that was fixed.
        fix_description: Description of what fix was applied.
    """
    agent = create_verification_agent()

    prompt = f"""Verify that the following fix was successful:

Pipeline: {pipeline_name}
Fix Applied: {fix_description}

Verification steps:
1. Check the current pipeline status for {pipeline_name} and its downstream dependencies.
2. Run diagnostic SQL queries to verify the specific fix (e.g., check if the column exists, null rates are acceptable).
3. Check data quality results for the pipeline.
4. Report whether the fix is verified or not.

Log your verification result using log_agent_action."""

    response = agent(prompt)
    return str(response)


if __name__ == "__main__":
    print(verify_fix(
        "stg_orders",
        "Added discount_amount column to stg_orders dbt model"
    ))

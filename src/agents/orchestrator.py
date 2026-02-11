"""
Orchestrator Agent: Coordinates Monitor -> Diagnostics -> Repair -> Verify pipeline.

This is the main entry point that ties all agents together.
It decides when to escalate vs auto-handle, and maintains
the overall workflow state.
"""

import json
from strands import Agent
from strands.models import BedrockModel
from src.config.settings import settings
from src.agents.monitor import create_monitor_agent, run_health_check
from src.agents.diagnostics import create_diagnostics_agent, diagnose_alert
from src.agents.repair import create_repair_agent, propose_fix
from src.agents.verification import create_verification_agent, verify_fix
from src.mcp_server.tools import get_pipeline_status, log_agent_action


ORCHESTRATOR_SYSTEM_PROMPT = """You are the Orchestrator for Agentic Pipeline Repair. You coordinate the full
pipeline incident response workflow with 5 agents.

IMPORTANT: Do not use emojis in your responses. Use plain text indicators like [PASS], [FAIL], [WARNING], [OK] instead.

AGENTS:
- Monitor Agent: Detects failures, SLA breaches, schema drift, quality issues
- Diagnostics Agent: Root cause analysis with extended thinking
- Repair Agent: Proposes and applies dbt model fixes
- Verification Agent: Confirms fixes resolved the issue
- You (Orchestrator): Coordinates the workflow

WORKFLOW:
1. MONITOR: Run health checks to detect issues
2. TRIAGE: Assess severity and decide on response
3. DIAGNOSE: For non-trivial issues, get root cause analysis (includes pattern history)
4. REPAIR: Propose fixes, apply with approval, run dbt to compile
5. VERIFY: Confirm the fix worked by checking pipeline status and quality
6. LEARN: Check failure patterns to identify recurring issues

You have access to all tools. Key capabilities:
- apply_dbt_model_fix: Write fixes directly to dbt model files (ask for approval first)
- run_dbt_model: Run dbt to compile and test after applying a fix
- rollback_dbt_model: Revert if a fix doesn't work
- get_failure_patterns: Identify recurring issues across pipelines
- get_agent_action_history: Review past actions for context

DECISION RULES:
- CRITICAL alerts: Full diagnosis + repair + auto-apply with approval + verify
- WARNING alerts: Diagnosis + propose fix (don't auto-apply)
- INFO alerts: Log and monitor

Always be transparent about confidence levels and ask for approval before applying fixes.
"""


class PipelineOrchestrator:
    """Main orchestrator that runs the agent pipeline."""

    def __init__(self):
        self.monitor = create_monitor_agent()
        self.diagnostics = create_diagnostics_agent()
        self.repair = create_repair_agent()
        self.verification = create_verification_agent()

    def run_full_check(self) -> dict:
        """Run a complete health check -> diagnose -> repair cycle."""
        results = {
            "health_check": None,
            "alerts": [],
            "diagnoses": [],
            "fix_proposals": [],
            "summary": "",
        }

        print("[MONITOR] Running pipeline health check...")
        health_result = run_health_check()
        results["health_check"] = health_result
        print("   Health check complete.")

        return results

    def handle_alert(self, alert: dict) -> dict:
        """Handle a specific alert through the full pipeline."""
        result = {"alert": alert, "diagnosis": None, "fix_proposal": None, "verification": None}

        print(f"[DIAGNOSTICS] Diagnosing: {alert.get('pipeline_name', 'unknown')}...")
        diagnosis = diagnose_alert(alert)
        result["diagnosis"] = diagnosis
        print("   Diagnosis complete.")

        print("[REPAIR] Generating fix proposal...")
        fix = propose_fix(
            {
                "root_cause": diagnosis,
                "affected_pipelines": [alert.get("pipeline_name")],
                "evidence": alert.get("description", ""),
                "recommended_fix": "Determine from diagnosis",
            }
        )
        result["fix_proposal"] = fix
        print("   Fix proposal ready.")

        return result

    def interactive_session(self):
        """Run an interactive session where users can ask questions about pipelines."""
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

        from src.mcp_server.tools import ALL_TOOLS

        agent = Agent(
            model=model,
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            tools=ALL_TOOLS,
        )

        print("\nAgentic Pipeline Repair")
        print("=" * 50)
        print("I can help you monitor, diagnose, and fix pipeline issues.")
        print("Commands: 'check' (health scan), 'patterns' (failure history), 'quit' (exit)\n")

        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break
            if user_input.lower() == "check":
                user_input = """Run a comprehensive health check on all pipelines:
1. Check pipeline status for failures, SLA breaches, or stuck runs.
2. Use get_monitored_tables to discover tracked tables, then check each for schema drift.
3. Use get_pipelines_with_quality_checks to discover which pipelines have quality checks, then check results for EACH one. Pipelines can show 'success' but still have FAILING quality checks.
4. Report ALL issues found including quality check failures."""
            elif user_input.lower() == "patterns":
                user_input = """Analyze failure patterns across all pipelines:
1. Use get_failure_patterns to see which pipelines fail most frequently.
2. Use get_agent_action_history to review recent agent actions.
3. Identify recurring issues and recommend preventive measures."""

            print("\nThinking...\n")
            response = agent(user_input)
            print(f"\nAgent: {response}\n")


if __name__ == "__main__":
    orchestrator = PipelineOrchestrator()
    orchestrator.interactive_session()

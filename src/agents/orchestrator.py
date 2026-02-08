"""
Orchestrator Agent: Coordinates Monitor -> Diagnostics -> Repair pipeline.

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
from src.mcp_server.tools import get_pipeline_status, log_agent_action


ORCHESTRATOR_SYSTEM_PROMPT = """You are the Orchestrator for Agentic Pipeline Repair. You coordinate the full
pipeline incident response workflow:

WORKFLOW:
1. MONITOR: Run health checks to detect issues
2. TRIAGE: Assess severity and decide on response
3. DIAGNOSE: For non-trivial issues, get root cause analysis
4. REPAIR: Get fix proposals for diagnosed issues
5. REPORT: Summarize findings and recommendations for the user

DECISION RULES:
- CRITICAL alerts: Always run full diagnosis + repair proposal
- WARNING alerts: Run diagnosis, propose fix only if confidence > 0.7
- INFO alerts: Log and monitor, no immediate action needed

You communicate results clearly to the user, showing:
- What was detected
- What the root cause is
- What fix is proposed
- Whether it needs human approval

Always be transparent about confidence levels and uncertainties.
"""


class PipelineOrchestrator:
    """Main orchestrator that runs the agent pipeline."""

    def __init__(self):
        self.monitor = create_monitor_agent()
        self.diagnostics = create_diagnostics_agent()
        self.repair = create_repair_agent()

    def run_full_check(self) -> dict:
        """Run a complete health check -> diagnose -> repair cycle."""
        results = {
            "health_check": None,
            "alerts": [],
            "diagnoses": [],
            "fix_proposals": [],
            "summary": "",
        }

        # Step 1: Health check
        print("🔍 Running pipeline health check...")
        health_result = run_health_check()
        results["health_check"] = health_result
        print(f"   Health check complete.")

        return results

    def handle_alert(self, alert: dict) -> dict:
        """Handle a specific alert through the full pipeline."""
        result = {"alert": alert, "diagnosis": None, "fix_proposal": None}

        # Step 1: Diagnose
        print(f"🔬 Diagnosing: {alert.get('pipeline_name', 'unknown')}...")
        diagnosis = diagnose_alert(alert)
        result["diagnosis"] = diagnosis
        print(f"   Diagnosis complete.")

        # Step 2: Propose fix
        print(f"🔧 Generating fix proposal...")
        fix = propose_fix(
            {
                "root_cause": diagnosis,
                "affected_pipelines": [alert.get("pipeline_name")],
                "evidence": alert.get("description", ""),
                "recommended_fix": "Determine from diagnosis",
            }
        )
        result["fix_proposal"] = fix
        print(f"   Fix proposal ready.")

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

        print("\n🤖 Agentic Pipeline Repair")
        print("=" * 50)
        print("I can help you monitor, diagnose, and fix pipeline issues.")
        print("Type 'quit' to exit, 'check' for a full health scan.\n")

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
            print("\n🤖 Thinking...\n")
            response = agent(user_input)
            print(f"\nAgent: {response}\n")


if __name__ == "__main__":
    orchestrator = PipelineOrchestrator()
    orchestrator.interactive_session()

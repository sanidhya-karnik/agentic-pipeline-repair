"""
Rich CLI for Agentic Pipeline Repair - Beautiful terminal interface for demos.

Features:
- Styled header and prompts
- Real-time tool call display (from strands)
- Markdown rendering for agent responses
- Color-coded panels

Usage:
    python -m src.agents.rich_cli
"""

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text
from rich.box import ROUNDED, HEAVY

console = Console()

# Color scheme  
COLORS = {
    "primary": "#3b82f6",
    "success": "#10b981", 
    "warning": "#f59e0b",
    "error": "#ef4444",
    "purple": "#8b5cf6",
    "cyan": "#06b6d4",
    "muted": "#64748b",
}


def print_header():
    """Print the application header."""
    title = Text()
    title.append("Agentic Pipeline Repair", style=f"bold {COLORS['primary']}")
    
    subtitle = Text()
    subtitle.append("Multi-agent data pipeline monitoring powered by ", style="dim")
    subtitle.append("Amazon Nova 2 Lite", style=f"bold {COLORS['cyan']}")
    
    console.print()
    console.print(Panel(
        title,
        subtitle=subtitle,
        border_style=COLORS['primary'],
        box=HEAVY,
        padding=(1, 4),
    ))
    console.print()


def print_commands():
    """Print available commands."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Command", style=f"bold {COLORS['success']}", min_width=10)
    table.add_column("Description", style="white")
    table.add_row("check", "Run comprehensive health scan on all pipelines")
    table.add_row("patterns", "Analyze historical failure patterns")
    table.add_row("clear", "Clear the screen")
    table.add_row("quit", "Exit the application")
    
    console.print(Panel(
        table, 
        title="[bold]Commands[/bold]", 
        border_style=COLORS['muted'], 
        box=ROUNDED, 
        padding=(0, 1)
    ))
    console.print()


def print_thinking():
    """Print thinking indicator."""
    console.print()
    console.print(Panel(
        Text("Analyzing...", style=f"bold {COLORS['cyan']}"),
        border_style=COLORS['cyan'],
        box=ROUNDED,
        padding=(0, 2),
    ))
    console.print()


def print_response(response: str):
    """Print the agent response with markdown formatting."""
    console.print()
    try:
        md = Markdown(str(response))
        console.print(Panel(
            md,
            title=f"[bold {COLORS['success']}]Agent Response[/bold {COLORS['success']}]",
            border_style=COLORS['success'],
            box=ROUNDED,
            padding=(1, 2),
        ))
    except:
        console.print(Panel(
            str(response),
            title=f"[bold {COLORS['success']}]Agent Response[/bold {COLORS['success']}]",
            border_style=COLORS['success'],
            box=ROUNDED,
            padding=(1, 2),
        ))
    console.print()


def get_user_input() -> str:
    """Get styled user input."""
    console.print()
    try:
        user_input = console.input(f"[bold {COLORS['primary']}]You >[/bold {COLORS['primary']}] ")
        return user_input.strip()
    except (EOFError, KeyboardInterrupt):
        return "quit"


def run_rich_cli():
    """Run the rich CLI interface."""
    from strands import Agent
    from strands.models import BedrockModel
    from src.config.settings import settings
    from src.mcp_server.tools import ALL_TOOLS
    
    # Clear screen and print header
    console.clear()
    print_header()
    print_commands()
    
    # Initialize model
    with console.status(f"[bold {COLORS['cyan']}]Initializing Amazon Nova 2 Lite...[/bold {COLORS['cyan']}]", spinner="dots"):
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
    
    SYSTEM_PROMPT = """You are the Orchestrator for Agentic Pipeline Repair. You coordinate the full
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
3. DIAGNOSE: For non-trivial issues, get root cause analysis
4. REPAIR: Propose fixes, apply with approval, run dbt to compile
5. VERIFY: Confirm the fix worked by checking pipeline status and quality

You have access to all tools. Key capabilities:
- apply_dbt_model_fix: Write fixes directly to dbt model files (ask for approval first)
- run_dbt_model: Run dbt to compile and test after applying a fix
- rollback_dbt_model: Revert if a fix doesn't work
- get_failure_patterns: Identify recurring issues across pipelines

DECISION RULES:
- CRITICAL alerts: Full diagnosis + repair + auto-apply with approval + verify
- WARNING alerts: Diagnosis + propose fix (don't auto-apply)
- INFO alerts: Log and monitor

Always be transparent about confidence levels and ask for approval before applying fixes.
"""
    
    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=ALL_TOOLS,
    )
    
    console.print(f"[bold {COLORS['success']}]Ready[/bold {COLORS['success']}]")
    
    # Main loop
    while True:
        user_input = get_user_input()
        
        if user_input.lower() in ("quit", "exit", "q"):
            console.print()
            console.print(Panel(
                Text("Goodbye!", style="bold white"),
                border_style=COLORS['primary'],
                box=ROUNDED,
            ))
            break
        
        if not user_input:
            continue
        
        # Handle shortcuts
        if user_input.lower() == "check":
            user_input = """Run a comprehensive health check on all pipelines:
1. Check pipeline status for failures, SLA breaches, or stuck runs.
2. Use get_monitored_tables to discover tracked tables, then check each for schema drift.
3. Use get_pipelines_with_quality_checks to discover which pipelines have quality checks, then check results for EACH one.
4. Report ALL issues found including quality check failures."""
        elif user_input.lower() == "patterns":
            user_input = """Analyze failure patterns across all pipelines:
1. Use get_failure_patterns to see which pipelines fail most frequently.
2. Use get_agent_action_history to review recent agent actions.
3. Identify recurring issues and recommend preventive measures."""
        elif user_input.lower() == "clear":
            console.clear()
            print_header()
            continue
        elif user_input.lower() == "help":
            print_commands()
            continue
        
        print_thinking()
        
        try:
            response = agent(user_input)
            print_response(str(response))
        except KeyboardInterrupt:
            console.print(f"\n[{COLORS['warning']}]Interrupted[/{COLORS['warning']}]")
        except Exception as e:
            console.print(Panel(
                f"[bold {COLORS['error']}]Error:[/bold {COLORS['error']}] {str(e)}",
                border_style=COLORS['error'],
                box=ROUNDED,
            ))


if __name__ == "__main__":
    run_rich_cli()

"""
FastAPI application for Agentic Pipeline Repair.

Endpoints:
- GET  /health             - App health check
- GET  /pipelines          - List all pipelines with status
- GET  /pipelines/{name}   - Pipeline detail with run history
- POST /check              - Trigger a full health check
- POST /diagnose           - Diagnose a specific alert
- POST /repair             - Get fix proposal for a diagnosis
- POST /chat               - Interactive chat with orchestrator
- GET  /actions            - Recent agent actions log
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import json

from src.config.settings import settings
from src.config.db import execute_query
from src.agents.orchestrator import PipelineOrchestrator
from src.agents.monitor import run_health_check
from src.agents.diagnostics import diagnose_alert
from src.agents.repair import propose_fix
from src.agents.verification import verify_fix
from src.agents.scheduler import scheduler

app = FastAPI(
    title="Agentic Pipeline Repair API",
    description="Multi-agent data pipeline repair system powered by Amazon Nova 2 Lite",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = PipelineOrchestrator()


# ---- Request/Response Models ----

class AlertRequest(BaseModel):
    pipeline_name: str
    alert_type: str = "pipeline_failure"
    severity: str = "CRITICAL"
    description: str


class DiagnosisRequest(BaseModel):
    root_cause: str
    affected_pipelines: list[str]
    evidence: str = ""
    recommended_fix: str = ""


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


# ---- Endpoints ----

@app.get("/health")
def health_check():
    """App health check."""
    return {"status": "ok", "model": settings.NOVA_MODEL_ID}


@app.get("/pipelines")
def list_pipelines():
    """List all pipelines with their current status."""
    sql = """
        SELECT
            p.pipeline_id, p.pipeline_name, p.description, p.schedule,
            p.sla_minutes, p.owner,
            lr.status AS last_run_status,
            lr.started_at AS last_run_at,
            lr.duration_seconds,
            lr.error_message
        FROM pipeline_meta.pipelines p
        LEFT JOIN LATERAL (
            SELECT * FROM pipeline_meta.pipeline_runs pr
            WHERE pr.pipeline_id = p.pipeline_id
            ORDER BY pr.started_at DESC LIMIT 1
        ) lr ON true
        WHERE p.is_active = true
        ORDER BY p.pipeline_name;
    """
    results = execute_query(sql)
    return {"pipelines": results}


@app.get("/pipelines/{pipeline_name}")
def get_pipeline_detail(pipeline_name: str):
    """Get detailed info for a specific pipeline."""
    # Pipeline info
    pipeline_sql = """
        SELECT * FROM pipeline_meta.pipelines WHERE pipeline_name = %s;
    """
    pipeline = execute_query(pipeline_sql, (pipeline_name,))
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline_name}' not found")

    # Recent runs
    runs_sql = """
        SELECT * FROM pipeline_meta.pipeline_runs pr
        JOIN pipeline_meta.pipelines p ON p.pipeline_id = pr.pipeline_id
        WHERE p.pipeline_name = %s
        ORDER BY pr.started_at DESC LIMIT 20;
    """
    runs = execute_query(runs_sql, (pipeline_name,))

    # Dependencies
    deps_sql = """
        SELECT p2.pipeline_name AS depends_on
        FROM pipeline_meta.dependencies d
        JOIN pipeline_meta.pipelines p ON p.pipeline_id = d.pipeline_id
        JOIN pipeline_meta.pipelines p2 ON p2.pipeline_id = d.depends_on_pipeline_id
        WHERE p.pipeline_name = %s;
    """
    deps = execute_query(deps_sql, (pipeline_name,))

    return {
        "pipeline": pipeline[0],
        "recent_runs": runs,
        "dependencies": [d["depends_on"] for d in deps],
    }


@app.post("/check")
def trigger_health_check():
    """Trigger a full pipeline health check via the Monitor Agent."""
    from src.config.db import execute_write
    result = run_health_check()
    # Always log the health check action so it shows in the dashboard
    try:
        summary = str(result)[:500] if result else "Health check completed"
        execute_write("""
            INSERT INTO pipeline_meta.agent_actions
                (agent_name, action_type, summary, confidence_score)
            VALUES ('monitor', 'health_check', %s, 0.95)
        """, (summary,))
    except Exception:
        pass
    return {"result": result}


@app.post("/diagnose")
def diagnose(alert: AlertRequest):
    """Diagnose a specific pipeline alert."""
    result = diagnose_alert(alert.model_dump())
    return {"diagnosis": result}


@app.post("/repair")
def repair(diagnosis: DiagnosisRequest):
    """Generate a fix proposal for a diagnosed issue."""
    result = propose_fix(diagnosis.model_dump())
    return {"fix_proposal": result}


# ---- Persistent Chat Agent ----

import threading
from strands import Agent
from strands.models import BedrockModel
from src.mcp_server.tools import ALL_TOOLS

CHAT_PROMPT = """You are the Orchestrator for Agentic Pipeline Repair, running in a web chat.

You help users monitor, diagnose, and repair data pipeline issues.

RULES:
- Be concise. Keep responses short and actionable.
- Use at most 8 tool calls per message. Do not over-investigate.
- For status checks: call get_pipeline_status, summarize, and ask what to investigate.
- For diagnosis: focus on the specific pipeline asked about.
- For fixes: read the dbt model, propose the fix, and wait for approval before applying.
- When user approves: call apply_dbt_model_fix then run_dbt_model to verify.
"""

_chat_agent = None

def _get_chat_agent():
    global _chat_agent
    if _chat_agent is None:
        model = BedrockModel(
            model_id=settings.NOVA_MODEL_ID,
            region_name=settings.AWS_REGION,
            additional_request_fields={
                "reasoningConfig": {"type": "enabled", "maxReasoningEffort": "medium"}
            },
        )
        _chat_agent = Agent(model=model, system_prompt=CHAT_PROMPT, tools=ALL_TOOLS)
    return _chat_agent


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Interactive chat with persistent conversation history."""
    agent = _get_chat_agent()
    result = {"response": ""}
    error = {"msg": None}

    def run():
        try:
            result["response"] = str(agent(request.message))
        except Exception as e:
            error["msg"] = str(e)

    t = threading.Thread(target=run)
    t.start()
    t.join(timeout=120)

    if t.is_alive():
        return ChatResponse(response="Request timed out. Try a more specific question.")
    if error["msg"]:
        return ChatResponse(response=f"Error: {error['msg']}")
    return ChatResponse(response=result["response"])


@app.post("/chat/reset")
def reset_chat():
    """Reset chat agent and conversation history."""
    global _chat_agent
    _chat_agent = None
    return {"status": "reset"}


@app.get("/actions")
def get_recent_actions(limit: int = 50):
    """Get recent agent actions for the dashboard."""
    sql = """
        SELECT
            aa.action_id, aa.agent_name, aa.action_type,
            p.pipeline_name, aa.summary, aa.details,
            aa.confidence_score, aa.status, aa.created_at
        FROM pipeline_meta.agent_actions aa
        LEFT JOIN pipeline_meta.pipelines p ON p.pipeline_id = aa.pipeline_id
        ORDER BY aa.created_at DESC
        LIMIT %s;
    """
    results = execute_query(sql, (limit,))
    return {"actions": results}


# ---- Verification ----

class VerifyRequest(BaseModel):
    pipeline_name: str
    fix_description: str


@app.post("/verify")
def verify(request: VerifyRequest):
    """Verify that an applied fix resolved the issue."""
    result = verify_fix(request.pipeline_name, request.fix_description)
    return {"verification": result}


# ---- Scheduler ----

@app.post("/scheduler/start")
def start_scheduler(interval_minutes: int = 5):
    """Start automated pipeline health checks."""
    scheduler.interval = interval_minutes * 60
    scheduler.start()
    return scheduler.status()


@app.post("/scheduler/stop")
def stop_scheduler():
    """Stop automated pipeline health checks."""
    scheduler.stop()
    return scheduler.status()


@app.get("/scheduler/status")
def scheduler_status():
    """Get scheduler status."""
    return scheduler.status()


# ---- Failure Patterns ----

@app.get("/patterns")
def get_patterns():
    """Get historical failure patterns across all pipelines."""
    from src.mcp_server.tools import get_failure_patterns
    result = get_failure_patterns.fn()
    return {"patterns": json.loads(result)}


# ---- Dashboard ----

DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "dashboard"


@app.get("/")
def serve_dashboard():
    """Serve the React dashboard."""
    index_path = DASHBOARD_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Dashboard not found. Place index.html in /dashboard/"}

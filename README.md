# Agentic Pipeline Repair

An autonomous multi-agent system that monitors, diagnoses, and repairs data pipeline failures using Amazon Nova 2 Lite's reasoning capabilities on Amazon Bedrock.

**Amazon Nova AI Hackathon 2026 | Category: Agentic AI**

## Architecture

```
┌─────────────────────────────────────┐
│         FastAPI Gateway             │
│        (Dashboard + API)            │
└─────────────────┬───────────────────┘
                  │
       ┌──────────▼──────────┐
       │  Orchestrator Agent │
       │  (Strands SDK)      │
       └─┬──────┬────────┬───┘
         │      │        │
       ┌─▼─┐ ┌──▼──┐ ┌───▼───┐
       │Mon│ │Diag │ │Repair │
       └──┬┘ └──┬──┘ └───┬───┘
          │     │        │
       ┌──▼─────▼────────▼───┐
       │  Amazon Bedrock     │
       │  Nova 2 Lite        │
       └─────────────────────┘
                 │
       ┌─────────▼───────────┐
       │  PostgreSQL + dbt   │
       │  (Pipeline Infra)   │
       └─────────────────────┘
```

## Tech Stack

- **LLM**: Amazon Nova 2 Lite via Amazon Bedrock (extended thinking)
- **Agent Framework**: Strands Agents SDK
- **Tool Protocol**: MCP (Model Context Protocol)
- **Backend**: FastAPI
- **Database**: PostgreSQL
- **Data Transforms**: dbt (dbt-postgres)
- **Infrastructure**: Docker Compose

## Agent Tools (11 total)

The agents interact with pipeline infrastructure through these tools:

- **get_pipeline_status** - Current state of all pipelines with SLA tracking
- **get_pipeline_dag** - Dependency graph (upstream/downstream) for any pipeline
- **get_run_history** - Recent run history with status, duration, errors
- **get_schema_info** - Table schemas with drift detection against snapshots
- **get_quality_checks** - Data quality check definitions and latest results
- **list_dbt_models** - Discover all dbt models in the project with categories
- **get_dbt_model_sql** - Read actual dbt model SQL so agents can understand and propose fixes
- **get_monitored_tables** - Dynamically discover all tables tracked for schema drift
- **get_pipelines_with_quality_checks** - Dynamically discover pipelines with quality checks
- **execute_diagnostic_sql** - Run read-only SQL queries for investigation
- **log_agent_action** - Record agent actions for audit trail

Agents discover what to monitor at runtime using `get_monitored_tables` and `get_pipelines_with_quality_checks`, making the system work with any dataset without code changes.

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+
- AWS CLI configured with Bedrock access (`AmazonBedrockFullAccess` policy)

### 1. Clone and configure
```bash
git clone <repo-url>
cd agentic-pipeline-repair
cp .env.example .env
# Edit .env with your AWS credentials and region
```

### 2. Start PostgreSQL
```bash
docker compose up -d postgres
```
This automatically creates the database schema, seeds synthetic e-commerce data (50 customers, 500 orders, 20 products), and populates pipeline metadata (10 pipelines with DAG dependencies, quality checks, and run history).

### 3. Install Python dependencies
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### 4. Initialize dbt models
```bash
cd dbt_project
dbt run --profiles-dir .
cd ..
```

### 5. Run the interactive agent
```bash
python -m src.agents.orchestrator
```

### 6. Try a health check
Type `check` at the prompt to run a full pipeline scan, or ask natural language questions like:
- "Why did mart_revenue_daily fail?"
- "Check data quality for stg_orders"
- "Propose a fix for the schema drift issue"

### 7. (Optional) Start the REST API
```bash
uvicorn src.api.main:app --reload --port 8000
```
API docs available at http://localhost:8000/docs

## Demo Scenarios

Inject simulated failures to demonstrate the agents in action:

```bash
# Scenario 1: Upstream schema change breaks downstream pipelines
python -m demo.inject_failure --scenario schema_drift

# Scenario 2: Null spike in a critical field (15% vs 5% threshold)
python -m demo.inject_failure --scenario data_quality

# Scenario 3: Pipeline stuck running 3x over SLA
python -m demo.inject_failure --scenario sla_breach

# Inject all three at once
python -m demo.inject_failure --scenario all

# Reset to clean state
python -m demo.inject_failure --scenario reset
```

## How It Works

1. **Monitor Agent** scans all pipelines for failures, SLA breaches, schema drift, and data quality violations. It dynamically discovers what to check from the database.

2. **Diagnostics Agent** uses Nova 2 Lite's extended thinking (high intensity) to perform root cause analysis. It traces the pipeline DAG upstream, examines run logs, and runs diagnostic SQL to build evidence.

3. **Repair Agent** generates concrete fix proposals: SQL patches, dbt model changes, and configuration updates. All fixes require human approval before application.

4. **Orchestrator Agent** coordinates the workflow and provides an interactive interface for users to ask questions and approve fixes.

## Project Structure

```
agentic-pipeline-repair/
├── README.md
├── docker-compose.yml
├── .env.example
├── requirements.txt
├── src/
│   ├── agents/
│   │   ├── monitor.py        # Detects pipeline issues
│   │   ├── diagnostics.py    # Root cause analysis with extended thinking
│   │   ├── repair.py         # Generates fix proposals using dbt model SQL
│   │   └── orchestrator.py   # Coordinates agents, interactive CLI
│   ├── mcp_server/
│   │   └── tools.py          # 11 MCP tools for pipeline interaction
│   ├── api/
│   │   └── main.py           # FastAPI REST endpoints
│   └── config/
│       ├── settings.py       # Environment-based configuration
│       └── db.py             # PostgreSQL query utilities
├── dbt_project/
│   ├── dbt_project.yml       # dbt configuration
│   ├── profiles.yml          # Database connection profile
│   └── models/
│       ├── staging/          # Staging models (stg_customers, stg_orders, etc.)
│       └── marts/            # Mart models (customer_orders, revenue, product perf.)
├── data/
│   └── sql/
│       └── init.sql          # Database schema + seed data
└── demo/
    └── inject_failure.py     # Demo scenario injection scripts
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | App health check |
| GET | /pipelines | List all pipelines with status |
| GET | /pipelines/{name} | Pipeline detail with run history |
| POST | /check | Trigger full health check |
| POST | /diagnose | Diagnose a specific alert |
| POST | /repair | Get fix proposal for a diagnosis |
| POST | /chat | Interactive chat with orchestrator |
| GET | /actions | Recent agent actions log |

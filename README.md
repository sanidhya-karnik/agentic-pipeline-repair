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
- **Data Transforms**: dbt
- **Infrastructure**: Docker Compose

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- AWS CLI configured with Bedrock access

### 1. Clone and configure
```bash
git clone https://github.com/sanidhya-karnik/agentic-pipeline-repair
cd agentic-pipeline-repair
cp .env.example .env
# Edit .env with your AWS credentials
```

### 2. Start infrastructure
```bash
docker compose up -d postgres
```

### 3. Install Python dependencies
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### 4. Initialize database and seed data
```bash
python -m src.config.init_db
```

### 5. Run dbt models
```bash
cd dbt_project
dbt run
cd ..
```

### 6. Start the application
```bash
# Terminal 1: Start MCP server
python -m src.mcp_server.server

# Terminal 2: Start FastAPI
uvicorn src.api.main:app --reload --port 8000
```

### 7. Trigger a demo scenario
```bash
# Inject a schema drift failure
python -m demo.inject_failure --scenario schema_drift
```

## Demo Scenarios

1. **Schema Drift**: Upstream table adds a column, downstream dbt model breaks
2. **Data Quality**: Null spike in a critical field
3. **SLA Violation**: Pipeline running 3x longer than normal

## Project Structure

```
agentic-pipeline-repair/
├── README.md
├── docker-compose.yml
├── .env.example
├── requirements.txt
├── src/
│   ├── agents/          # Strands agent definitions
│   │   ├── monitor.py
│   │   ├── diagnostics.py
│   │   ├── repair.py
│   │   └── orchestrator.py
│   ├── mcp_server/      # MCP tool server
│   │   └── server.py
│   ├── api/             # FastAPI endpoints
│   │   └── main.py
│   └── config/          # Configuration
│       ├── settings.py
│       └── init_db.py
├── data/sql/            # Database init scripts
├── dbt_project/         # dbt models
├── tests/
├── docs/
└── demo/                # Demo scenario scripts
```

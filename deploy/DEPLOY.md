# AWS Cloud Deployment Guide

Deploys Agentic Pipeline Repair to AWS using RDS PostgreSQL + EC2.

## Estimated Cost
- RDS db.t3.micro: ~$0.50/day
- EC2 t3.small: ~$0.50/day  
- Total: ~$1/day (well within $100 hackathon credits)

## Prerequisites
- AWS CLI v2 configured with your credentials
- `psql` client installed locally (for DB init)
- Git Bash or WSL on Windows (scripts are bash)

## Quick Deploy

### Option A: Automated (Linux/Mac/WSL)
```bash
cd agentic-pipeline-repair
bash deploy/setup_aws.sh
```
This creates everything and prints connection details.

### Option B: Manual (Step by Step)

#### 1. Create RDS PostgreSQL
Go to AWS Console > RDS > Create Database:
- Engine: PostgreSQL 16
- Template: Free tier
- DB instance identifier: `agentic-pipeline-db`
- Master username: `pipeline_admin`
- Master password: `<YOUR_DB_PASSWORD>`
- DB name: `pipeline_agent`
- Instance: db.t3.micro
- Public access: Yes
- Security group: Create new, allow port 5432 from your IP and EC2 SG

Wait for it to become "Available", then note the **Endpoint** (e.g., `agentic-pipeline-db.abc123.us-east-1.rds.amazonaws.com`).

#### 2. Initialize the Database
```bash
psql -h <RDS_ENDPOINT> -U pipeline_admin -d pipeline_agent -f data/sql/init.sql
```

#### 3. Launch EC2 Instance
Go to AWS Console > EC2 > Launch Instance:
- AMI: Ubuntu 22.04 LTS
- Instance type: t3.small
- Key pair: Create new, download .pem file
- Security group: Allow SSH (22) and Custom TCP (8000) from anywhere
- Also attach the same security group as RDS (or allow 5432 between them)

#### 4. SSH and Configure
```bash
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>

# Clone and setup
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv git postgresql-client
git clone https://github.com/sanidhya-karnik/agentic-pipeline-repair.git
cd agentic-pipeline-repair

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install dbt-postgres

# Configure environment
cp .env.example .env
nano .env
# Set:
#   POSTGRES_HOST=<RDS_ENDPOINT>
#   POSTGRES_PASSWORD=<YOUR_DB_PASSWORD>
#   AWS_ACCESS_KEY_ID=<your key>
#   AWS_SECRET_ACCESS_KEY=<your secret>

# Run dbt models
cd dbt_project
export POSTGRES_HOST=<RDS_ENDPOINT>
export POSTGRES_PASSWORD=<YOUR_DB_PASSWORD>
export POSTGRES_USER=pipeline_admin
export POSTGRES_DB=pipeline_agent
export POSTGRES_PORT=5432
dbt run --profiles-dir .
cd ..

# Start the server
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

#### 5. Access the App
- API docs: `http://<EC2_PUBLIC_IP>:8000/docs`
- Health check: `http://<EC2_PUBLIC_IP>:8000/health`
- Pipelines: `http://<EC2_PUBLIC_IP>:8000/pipelines`

## Running Demo Scenarios on Cloud
```bash
# SSH into EC2
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>

cd agentic-pipeline-repair
source .venv/bin/activate

# Inject a failure
python -m demo.inject_failure --scenario schema_drift

# Run the interactive agent
python -m src.agents.orchestrator
```

## Running as Background Service
To keep the API running after disconnecting SSH:
```bash
nohup uvicorn src.api.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
```
Check logs: `tail -f server.log`

## Teardown (Avoid Charges)
```bash
bash deploy/teardown_aws.sh
```
Or manually delete in AWS Console:
1. EC2 > Instances > Terminate
2. RDS > Databases > Delete (skip final snapshot)
3. EC2 > Security Groups > Delete
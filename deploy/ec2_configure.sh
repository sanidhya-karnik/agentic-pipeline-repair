#!/bin/bash
# ============================================================
# Run this AFTER SSH-ing into the EC2 instance
# Configures the app with RDS endpoint and starts the server
# ============================================================

set -e

if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ]; then
    echo "Usage: ./ec2_configure.sh <RDS_ENDPOINT> <AWS_ACCESS_KEY_ID> <AWS_SECRET_ACCESS_KEY>"
    echo ""
    echo "Example:"
    echo "  ./ec2_configure.sh agentic-pipeline-db.abc123.us-east-1.rds.amazonaws.com AKIA... wJal..."
    exit 1
fi

RDS_ENDPOINT=$1
AWS_ACCESS_KEY=$2
AWS_SECRET_KEY=$3

cd /home/ubuntu/agentic-pipeline-repair

echo "[1/4] Creating .env file..."
cat > .env << EOF
AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY
AWS_SECRET_ACCESS_KEY=$AWS_SECRET_KEY
AWS_DEFAULT_REGION=us-east-1
NOVA_MODEL_ID=us.amazon.nova-2-lite-v1:0
POSTGRES_HOST=$RDS_ENDPOINT
POSTGRES_PORT=5432
POSTGRES_DB=pipeline_agent
POSTGRES_USER=pipeline_admin
POSTGRES_PASSWORD=<YOUR_DB_PASSWORD>
APP_ENV=production
LOG_LEVEL=INFO
EOF
echo "  .env created."

echo "[2/4] Activating virtual environment..."
source .venv/bin/activate

echo "[3/4] Running dbt models..."
cd dbt_project
export POSTGRES_HOST=$RDS_ENDPOINT
export POSTGRES_PORT=5432
export POSTGRES_DB=pipeline_agent
export POSTGRES_USER=pipeline_admin
export POSTGRES_PASSWORD=hackathon2026secure
pip install dbt-postgres 2>/dev/null
dbt run --profiles-dir .
cd ..

echo "[4/4] Starting FastAPI server..."
echo ""
echo "Starting server on port 8000..."
echo "Access the API at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000/docs"
echo ""
echo "Press Ctrl+C to stop the server."
echo ""
nohup uvicorn src.api.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
echo "Server started in background. Logs: tail -f server.log"

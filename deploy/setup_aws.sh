#!/bin/bash
# ============================================================
# Agentic Pipeline Repair - AWS Infrastructure Setup
# Creates: VPC Security Group, RDS PostgreSQL, EC2 Instance
# Region: us-east-1
# ============================================================

set -e

# --- Configuration ---
AWS_REGION="us-east-1"
DB_INSTANCE_ID="agentic-pipeline-db"
DB_NAME="pipeline_agent"
DB_USER="pipeline_admin"
DB_PASSWORD="hackathon2026secure"
DB_INSTANCE_CLASS="db.t3.micro"

EC2_KEY_NAME="agentic-pipeline-key"
EC2_INSTANCE_TYPE="t3.small"
EC2_AMI="ami-0c7217cdde317cfec"  # Ubuntu 22.04 LTS us-east-1 (update if needed)

SG_NAME="agentic-pipeline-sg"
PROJECT_NAME="agentic-pipeline-repair"

echo "============================================"
echo " Agentic Pipeline Repair - AWS Setup"
echo " Region: $AWS_REGION"
echo "============================================"

# --- Step 1: Create Key Pair ---
echo ""
echo "[1/5] Creating EC2 key pair..."
aws ec2 create-key-pair \
    --key-name $EC2_KEY_NAME \
    --query 'KeyMaterial' \
    --output text \
    --region $AWS_REGION > ${EC2_KEY_NAME}.pem

chmod 400 ${EC2_KEY_NAME}.pem
echo "  Key saved to ${EC2_KEY_NAME}.pem"

# --- Step 2: Create Security Group ---
echo ""
echo "[2/5] Creating security group..."
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" \
    --query 'Vpcs[0].VpcId' --output text --region $AWS_REGION)

SG_ID=$(aws ec2 create-security-group \
    --group-name $SG_NAME \
    --description "Security group for Agentic Pipeline Repair" \
    --vpc-id $VPC_ID \
    --query 'GroupId' --output text --region $AWS_REGION)

# Allow SSH
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID --protocol tcp --port 22 --cidr 0.0.0.0/0 --region $AWS_REGION

# Allow FastAPI (port 8000)
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID --protocol tcp --port 8000 --cidr 0.0.0.0/0 --region $AWS_REGION

# Allow PostgreSQL (within SG)
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID --protocol tcp --port 5432 --source-group $SG_ID --region $AWS_REGION

echo "  Security group: $SG_ID"

# --- Step 3: Create RDS PostgreSQL ---
echo ""
echo "[3/5] Creating RDS PostgreSQL instance (this takes ~5 minutes)..."
aws rds create-db-instance \
    --db-instance-identifier $DB_INSTANCE_ID \
    --db-instance-class $DB_INSTANCE_CLASS \
    --engine postgres \
    --engine-version "16.4" \
    --master-username $DB_USER \
    --master-user-password $DB_PASSWORD \
    --db-name $DB_NAME \
    --allocated-storage 20 \
    --vpc-security-group-ids $SG_ID \
    --publicly-accessible \
    --backup-retention-period 0 \
    --no-multi-az \
    --storage-type gp3 \
    --region $AWS_REGION \
    --tags Key=Project,Value=$PROJECT_NAME \
    --no-cli-pager

echo "  Waiting for RDS to become available..."
aws rds wait db-instance-available \
    --db-instance-identifier $DB_INSTANCE_ID --region $AWS_REGION

RDS_ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier $DB_INSTANCE_ID \
    --query 'DBInstances[0].Endpoint.Address' \
    --output text --region $AWS_REGION)

echo "  RDS endpoint: $RDS_ENDPOINT"

# --- Step 4: Initialize Database ---
echo ""
echo "[4/5] Initializing database with schema and seed data..."
PGPASSWORD=$DB_PASSWORD psql -h $RDS_ENDPOINT -U $DB_USER -d $DB_NAME -f data/sql/init.sql
echo "  Database initialized."

# --- Step 5: Launch EC2 Instance ---
echo ""
echo "[5/5] Launching EC2 instance..."

# Create user data script
cat > /tmp/ec2_userdata.sh << 'USERDATA'
#!/bin/bash
apt-get update -y
apt-get install -y python3-pip python3-venv git postgresql-client

cd /home/ubuntu
git clone https://github.com/sanidhya-karnik/agentic-pipeline-repair.git
cd agentic-pipeline-repair

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

echo "Setup complete. Configure .env and start the app."
USERDATA

INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $EC2_AMI \
    --instance-type $EC2_INSTANCE_TYPE \
    --key-name $EC2_KEY_NAME \
    --security-group-ids $SG_ID \
    --user-data file:///tmp/ec2_userdata.sh \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$PROJECT_NAME}]" \
    --region $AWS_REGION \
    --query 'Instances[0].InstanceId' --output text)

echo "  Waiting for EC2 instance to start..."
aws ec2 wait instance-running --instance-ids $INSTANCE_ID --region $AWS_REGION

EC2_PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text --region $AWS_REGION)

echo "  EC2 public IP: $EC2_PUBLIC_IP"

# --- Summary ---
echo ""
echo "============================================"
echo " Setup Complete!"
echo "============================================"
echo ""
echo " RDS Endpoint:  $RDS_ENDPOINT"
echo " EC2 Public IP: $EC2_PUBLIC_IP"
echo " EC2 Instance:  $INSTANCE_ID"
echo " Security Group: $SG_ID"
echo ""
echo " Next steps:"
echo " 1. SSH into EC2:"
echo "    ssh -i ${EC2_KEY_NAME}.pem ubuntu@${EC2_PUBLIC_IP}"
echo ""
echo " 2. Configure .env on EC2:"
echo "    cd agentic-pipeline-repair"
echo "    cp .env.example .env"
echo "    # Set POSTGRES_HOST=$RDS_ENDPOINT"
echo "    # Set your AWS keys"
echo ""
echo " 3. Start the app:"
echo "    source .venv/bin/activate"
echo "    uvicorn src.api.main:app --host 0.0.0.0 --port 8000"
echo ""
echo " 4. Access API: http://${EC2_PUBLIC_IP}:8000/docs"
echo "============================================"

# Save config for teardown
cat > deploy/aws_config.txt << EOF
AWS_REGION=$AWS_REGION
DB_INSTANCE_ID=$DB_INSTANCE_ID
EC2_INSTANCE_ID=$INSTANCE_ID
EC2_KEY_NAME=$EC2_KEY_NAME
SG_ID=$SG_ID
RDS_ENDPOINT=$RDS_ENDPOINT
EC2_PUBLIC_IP=$EC2_PUBLIC_IP
EOF
echo " Config saved to deploy/aws_config.txt"

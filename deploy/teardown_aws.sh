#!/bin/bash
# ============================================================
# Agentic Pipeline Repair - Teardown AWS Resources
# Run this to clean up and avoid charges
# ============================================================

set -e

if [ ! -f deploy/aws_config.txt ]; then
    echo "Error: deploy/aws_config.txt not found. Cannot teardown."
    exit 1
fi

source deploy/aws_config.txt

echo "============================================"
echo " Tearing down AWS resources..."
echo "============================================"

echo "[1/3] Terminating EC2 instance: $EC2_INSTANCE_ID"
aws ec2 terminate-instances --instance-ids $EC2_INSTANCE_ID --region $AWS_REGION --no-cli-pager
aws ec2 wait instance-terminated --instance-ids $EC2_INSTANCE_ID --region $AWS_REGION
echo "  EC2 terminated."

echo "[2/3] Deleting RDS instance: $DB_INSTANCE_ID"
aws rds delete-db-instance \
    --db-instance-identifier $DB_INSTANCE_ID \
    --skip-final-snapshot \
    --region $AWS_REGION --no-cli-pager
echo "  Waiting for RDS deletion (this takes a few minutes)..."
aws rds wait db-instance-deleted --db-instance-identifier $DB_INSTANCE_ID --region $AWS_REGION
echo "  RDS deleted."

echo "[3/3] Deleting security group: $SG_ID"
aws ec2 delete-security-group --group-id $SG_ID --region $AWS_REGION
echo "  Security group deleted."

echo ""
echo "Deleting key pair: $EC2_KEY_NAME"
aws ec2 delete-key-pair --key-name $EC2_KEY_NAME --region $AWS_REGION
rm -f ${EC2_KEY_NAME}.pem

echo ""
echo "============================================"
echo " Teardown complete. All resources removed."
echo "============================================"

#!/bin/bash
# AWS ECS Migration Script for THEO
# Usage: ./migrate-aws.sh

set -e

echo "🔍 Finding latest backend task..."
TASK_ID=$(aws ecs list-tasks \
  --cluster theo-prod \
  --service-name backend \
  --desired-status RUNNING \
  --query 'taskArns[0]' \
  --output text | awk -F'/' '{print $NF}')

if [ -z "$TASK_ID" ]; then
  echo "❌ No running backend tasks found"
  exit 1
fi

echo "✅ Found task: $TASK_ID"
echo ""
echo "🚀 Connecting to ECS task..."
echo "   Run this command inside the container:"
echo ""
echo "   cd /data && python3 /app/migrations/run_migrations.py theo.db"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

aws ecs execute-command \
  --cluster theo-prod \
  --task $TASK_ID \
  --container backend \
  --interactive \
  --command '/bin/sh'

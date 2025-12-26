# ECS Database Persistence Setup Guide

## What You've Already Done ✅
- Created S3 bucket: `theo-database-backups`
- Database backup code is ready in the backend

## What You Need To Do

### Step 1: Update ECS Task Role with S3 Permissions

Your ECS task needs permission to read/write to S3.

#### Option A: Using AWS Console

1. Go to **IAM Console** → **Roles**
2. Find your ECS Task Role (usually named something like `ecsTaskExecutionRole` or `theo-backend-task-role`)
3. Click **Add permissions** → **Create inline policy**
4. Click **JSON** tab
5. Paste the contents of `iam-policy-s3-database-backup.json`
6. Click **Review policy**
7. Name it: `TheoDatabaseBackupS3Access`
8. Click **Create policy**

#### Option B: Using AWS CLI

```bash
# Replace with your actual ECS task role name
TASK_ROLE_NAME="your-ecs-task-role-name"

# Attach the policy
aws iam put-role-policy \
  --role-name $TASK_ROLE_NAME \
  --policy-name TheoDatabaseBackupS3Access \
  --policy-document file://iam-policy-s3-database-backup.json
```

### Step 2: Update ECS Task Definition

1. Go to **ECS Console** → **Task Definitions**
2. Select your backend task definition
3. Click **Create new revision**
4. Scroll to **Container Definitions** → Click on your backend container
5. Scroll to **Environment Variables**
6. Add two new environment variables:
   - **Name**: `THEO_S3_BACKUP_BUCKET` | **Value**: `theo-database-backups`
   - **Name**: `THEO_S3_BACKUP_KEY` | **Value**: `theo/theo.db`
7. Click **Update**
8. Click **Create**

**OR** use the pre-configured file `ecs-task-definition-backend-UPDATED.json` to update via CLI:

```bash
aws ecs register-task-definition \
  --cli-input-json file://ecs-task-definition-backend-UPDATED.json
```

### Step 3: Update ECS Service

After creating the new task definition revision, update your service to use it:

1. Go to **ECS Console** → **Clusters** → Your cluster → **Services**
2. Select your backend service
3. Click **Update**
4. Under **Task Definition**, select the new revision (should be the latest)
5. Click **Update** at the bottom

**OR** via CLI:

```bash
# Replace with your actual values
CLUSTER_NAME="your-cluster-name"
SERVICE_NAME="your-backend-service-name"
TASK_DEF_FAMILY="your-task-def-family"  # Usually just "backend" or "theo-backend"

# Get the latest revision number
LATEST_REVISION=$(aws ecs describe-task-definition \
  --task-definition $TASK_DEF_FAMILY \
  --query 'taskDefinition.revision' \
  --output text)

# Update the service
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --task-definition ${TASK_DEF_FAMILY}:${LATEST_REVISION} \
  --force-new-deployment
```

### Step 4: Verify Setup

1. **Check Logs**: Once the new task starts, check CloudWatch logs for:
   ```
   Database backups enabled to s3://theo-database-backups/theo/theo.db
   No existing database backup found in S3 (first deployment)
   Database backed up successfully to S3
   ```

2. **Check S3**: After 5 minutes, verify the backup exists:
   ```bash
   aws s3 ls s3://theo-database-backups/theo/
   ```

   You should see: `theo.db`

3. **Test the Flow**:
   - Add a provider in THEO Settings
   - Wait 5 minutes (for automatic backup)
   - Verify backup in S3: `aws s3 ls s3://theo-database-backups/theo/theo.db`
   - Force a new deployment (restart the ECS service)
   - Check if your provider is still there after restart ✅

## Important Notes

### Finding Your ECS Task Role

Your task role is different from the task execution role. To find it:

1. Go to **ECS Console** → **Task Definitions** → Your backend task
2. Look for **Task Role** (not Task Execution Role)
3. If you don't have a task role set:
   - Create a new role: **IAM** → **Roles** → **Create role**
   - Select **AWS service** → **Elastic Container Service** → **Elastic Container Service Task**
   - Attach the S3 policy
   - Update your task definition to use this role

### Database Location

The code expects the database at `/data/theo.db` inside the container. Your current mount point is `/app/backend/data`, so you might need to adjust. Let me check your config:

**Current Mount**: `/app/backend/data` (from your task definition)
**Expected by Code**: `/data/theo.db` (from Dockerfile ENV)

You have two options:

**Option 1**: Update mount point in task definition (RECOMMENDED)
```json
"mountPoints": [
  {
    "containerPath": "/data",
    "readOnly": false,
    "sourceVolume": "theo-data"
  }
]
```

**Option 2**: Update environment variable in task definition
```json
{
  "name": "DATABASE_URL",
  "value": "sqlite:///app/backend/data/theo.db"
}
```

I recommend **Option 1** - it matches the Dockerfile configuration.

## Troubleshooting

### "Access Denied" errors in logs
→ The task role doesn't have S3 permissions. Double-check Step 1.

### "No such file or directory: /data/theo.db"
→ The mount point doesn't match. See "Database Location" section above.

### Database still disappears after deployment
→ Check that:
1. S3 bucket name is spelled correctly in environment variables
2. Task role has S3 permissions
3. Logs show "Database backed up successfully to S3"
4. The backup file exists in S3

## Cost

- **S3 Storage**: ~$0.002/month (database is typically < 100MB)
- **S3 Requests**: ~$0.04/month (backup every 5 minutes)
- **Total**: Less than $0.05/month

## Next Steps After Setup

Once working, you can:
- Enable S3 versioning for backup history
- Set up S3 lifecycle rules to archive old versions
- Configure S3 encryption at rest for security
- Reduce backup frequency if desired (edit `db_backup.py` line 114)

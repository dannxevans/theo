# Database Persistence on AWS

The THEO application uses SQLite for local development and can persist data on AWS deployments using S3 backups.

## Problem

By default, SQLite databases stored in Docker containers are lost when the container restarts or redeploys. This means:
- Provider configurations are lost
- Memory facts are lost
- Intent customizations are lost
- Session history is lost

## Solution: S3 Automatic Backup/Restore

The application now automatically:
1. **On Startup**: Restores the database from S3 (if backup exists)
2. **Every 5 Minutes**: Backs up the database to S3
3. **On Changes**: Database changes are automatically persisted

This ensures your data survives deployments, instance failures, and auto-scaling events.

## AWS Setup Instructions

### Step 1: Create S3 Bucket

1. Go to AWS S3 Console
2. Click "Create bucket"
3. Name it (e.g., `theo-database-backups`)
4. Choose your region (same as your EC2/ECS)
5. Keep default settings
6. Click "Create bucket"

### Step 2: Configure IAM Permissions

Your EC2 instance or ECS task needs permission to read/write to S3.

#### Option A: EC2 Instance Role (Recommended)

Add this policy to your EC2 instance role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::theo-database-backups",
        "arn:aws:s3:::theo-database-backups/*"
      ]
    }
  ]
}
```

#### Option B: ECS Task Role

If using ECS, add the same policy to your Task Role.

### Step 3: Set Environment Variables

Add these environment variables to your deployment:

```bash
# Required: S3 bucket name for database backups
THEO_S3_BACKUP_BUCKET=theo-database-backups

# Optional: Custom S3 key (defaults to "theo/theo.db")
THEO_S3_BACKUP_KEY=theo/theo.db
```

#### For EC2 User Data:

```bash
export THEO_S3_BACKUP_BUCKET=theo-database-backups
```

#### For ECS Task Definition:

```json
{
  "environment": [
    {
      "name": "THEO_S3_BACKUP_BUCKET",
      "value": "theo-database-backups"
    }
  ]
}
```

#### For Docker Compose:

```yaml
environment:
  - THEO_S3_BACKUP_BUCKET=theo-database-backups
```

## How It Works

### On Application Startup

1. Application checks if `THEO_S3_BACKUP_BUCKET` is set
2. If set, downloads `theo/theo.db` from S3 to `/data/theo.db`
3. If no backup exists (first deployment), starts with empty database
4. Starts automatic backup thread

### During Operation

1. Background thread runs every 5 minutes
2. Uploads current `/data/theo.db` to S3
3. Your providers, memories, and intents are safely backed up

### On Redeployment

1. New container starts
2. Downloads latest database from S3
3. All your data is restored
4. No manual intervention needed!

## Verification

### Check if Backups are Working

1. **View Logs**: Look for these log messages:
   ```
   Database backups enabled to s3://theo-database-backups/theo/theo.db
   Successfully restored database from S3
   Database backed up successfully to S3
   ```

2. **Check S3**: Verify the backup file exists in your bucket at `theo/theo.db`

3. **Test Restore**:
   - Add a provider or memory
   - Wait 5 minutes for backup
   - Redeploy your application
   - Verify the data is still there

## Troubleshooting

### "No existing database backup found in S3"

This is normal on first deployment. The database will be created and backed up automatically.

### "Failed to restore database from S3: Access Denied"

Your EC2 instance or ECS task doesn't have S3 permissions. Check Step 2 above.

### "Database backups disabled (no S3 bucket configured)"

The `THEO_S3_BACKUP_BUCKET` environment variable is not set. See Step 3 above.

## Alternative: EFS (For High-Frequency Writes)

If you have high-frequency database writes (many users, lots of chat messages), consider using EFS instead:

1. Create an EFS file system in AWS
2. Mount it to `/data` in your EC2/ECS configuration
3. Remove `THEO_S3_BACKUP_BUCKET` environment variable
4. Database will persist directly on EFS (no 5-minute delay)

## Backup Strategy

- **Automatic**: S3 backups every 5 minutes
- **Manual**: You can also manually backup via AWS CLI:
  ```bash
  aws s3 cp s3://theo-database-backups/theo/theo.db ./theo-backup-$(date +%Y%m%d).db
  ```

## Cost Estimate

- **S3 Storage**: $0.023/GB/month (database is typically < 100MB = ~$0.002/month)
- **S3 Requests**: ~8,640 PUT requests/month = ~$0.04/month
- **Total**: Less than $0.05/month for database persistence

## Security Notes

- Database file in S3 is not encrypted by default
- To encrypt: Enable S3 bucket encryption (AES-256 or KMS)
- IAM permissions ensure only your EC2/ECS can access the backup
- Never make the S3 bucket public

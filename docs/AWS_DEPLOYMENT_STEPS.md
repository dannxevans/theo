# AWS Deployment Steps - Mode Separation & PII Feature

## Post-Deployment Database Migration

After deploying the updated backend to AWS, you need to run the database migration to add the new columns.

---

## Step 1: SSH into AWS EC2 Instance

```bash
# Replace with your EC2 instance details
ssh -i /path/to/your-key.pem ec2-user@your-instance-ip

# Or if using SSM Session Manager
aws ssm start-session --target i-your-instance-id
```

---

## Step 2: Navigate to Application Directory

```bash
cd /path/to/theo/backend
# Usually something like:
# cd /var/app/current/backend
# or
# cd /home/ec2-user/theo/backend
```

---

## Step 3: Run Database Migration

```bash
# Run the migration script
python3 migrations/003_add_mode_to_sessions.py

# You should see output like:
# [MIGRATION 003] Starting migration...
# [MIGRATION 003] Database: /path/to/theo.db
# [MIGRATION 003] Adding mode column to sessions table...
# [MIGRATION 003] ✓ Added mode column
# [MIGRATION 003] Adding user_id column to sessions table...
# [MIGRATION 003] ✓ Added user_id column
# [MIGRATION 003] Adding pii_filtering_enabled column to mode_settings table...
# [MIGRATION 003] ✓ Added pii_filtering_enabled column
# [MIGRATION 003] Adding pii_redaction_config column to mode_settings table...
# [MIGRATION 003] ✓ Added pii_redaction_config column
# [MIGRATION 003] Creating composite index on sessions...
# [MIGRATION 003] ✓ Created index idx_sessions_user_mode_updated
# [MIGRATION 003] ✓ Migration completed successfully
```

---

## Step 4: Verify Migration

```bash
# Check that columns were added
sqlite3 /path/to/data/theo.db "PRAGMA table_info(sessions);" | grep -E "(mode|user_id)"

# Should output:
# 4|mode|TEXT|0|'personal'|0
# 5|user_id|INTEGER|0||0

# Check mode_settings table
sqlite3 /path/to/data/theo.db "PRAGMA table_info(mode_settings);" | grep -E "(pii_filtering|pii_redaction)"

# Should output:
# 8|pii_filtering_enabled|INTEGER|0|0|0
# 9|pii_redaction_config|TEXT|0||0
```

---

## Step 5: Restart Backend Service

```bash
# If using systemd
sudo systemctl restart theo-backend

# Or if using PM2
pm2 restart theo-backend

# Or if using Docker
docker restart theo-backend

# Or if running manually
pkill -f "python3.*app.py"
python3 app.py > /tmp/theo-backend.log 2>&1 &
```

---

## Step 6: Verify Backend is Running

```bash
# Check service status
sudo systemctl status theo-backend

# Or check logs
tail -f /var/log/theo/backend.log
# or
tail -f /tmp/theo-backend.log

# Test API endpoint
curl http://localhost:1066/health
# Should return: {"status": "ok"}

# Test sessions endpoint
curl -X GET http://localhost:1066/api/sessions \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
# Should return: []
```

---

## Step 7: Deploy Frontend (if needed)

If you haven't already deployed the frontend changes:

```bash
# On your local machine
cd frontend
npm run build

# Upload to S3 (if using S3 + CloudFront)
aws s3 sync dist/ s3://your-bucket-name/ --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/*"
```

---

## Troubleshooting

### Migration Fails

**Error**: `Database not found`
```bash
# Find the database location
find /var/app -name "theo.db" 2>/dev/null
find /home -name "theo.db" 2>/dev/null

# Run migration with explicit path
python3 migrations/003_add_mode_to_sessions.py /path/to/theo.db
```

**Error**: `Column already exists`
- This is safe to ignore - it means migration was already run
- Check output for "✓ already exists, skipping" messages

### Backend Won't Start

**Check Python dependencies**:
```bash
pip3 install -r requirements.txt
```

**Check for port conflicts**:
```bash
lsof -ti:1066
# If something is using the port
sudo kill -9 $(lsof -ti:1066)
```

**Check permissions**:
```bash
# Ensure database is writable
ls -la /path/to/data/theo.db
chmod 664 /path/to/data/theo.db
```

### Verify Feature is Working

**Test PII Config API**:
```bash
# Get PII config (should return default config)
curl -X GET http://localhost:1066/api/mode/settings/work/pii-config \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"

# Should return:
# {"pii_filtering_enabled": false, "pii_redaction_config": null}
```

**Test Mode Filtering**:
```bash
# Get sessions (filtered by mode)
curl -X GET http://localhost:1066/api/mode \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"

# Should return current mode:
# {"active_mode": "personal"}
```

---

## Rollback Plan (If Needed)

If something goes wrong, you can rollback:

```bash
# 1. Restore database backup (if you have one)
cp /path/to/backup/theo.db /path/to/data/theo.db

# 2. Revert code deployment
git checkout previous-commit-hash
python3 app.py

# 3. The migration is idempotent - columns are only added if missing
# So you can safely re-run it after fixing issues
```

---

## Environment Variables (Optional)

If you want to configure PII filtering defaults:

```bash
# Add to your environment file (.env or systemd service)
THEO_DEFAULT_PII_FILTERING=false
THEO_PII_REDACTION_TYPES=emails,phones,ssns,creditCards
```

---

## Post-Deployment Verification Checklist

Once deployed, verify these features work:

### Backend
- [ ] Migration completed successfully
- [ ] Backend starts without errors
- [ ] `/api/sessions` endpoint returns data
- [ ] `/api/mode` endpoint returns mode config
- [ ] `/api/mode/settings/work/pii-config` endpoint returns PII config

### Frontend
- [ ] Application loads without errors
- [ ] Settings → Work Mode shows PII Protection section
- [ ] Can enable/disable PII filtering
- [ ] Can save PII configuration
- [ ] Mode switching creates new chat
- [ ] Mode lock warning appears when selecting cross-mode chat
- [ ] "Working at OFFICIAL" badge shows in work mode

### Database
- [ ] `sessions` table has `mode` and `user_id` columns
- [ ] `mode_settings` table has PII columns
- [ ] Composite index exists: `idx_sessions_user_mode_updated`

---

## AWS-Specific Considerations

### RDS Database (if using RDS instead of SQLite)

If you're using RDS PostgreSQL instead of SQLite:

```bash
# Connect to RDS
psql -h your-rds-endpoint.rds.amazonaws.com -U postgres -d theo

# Run SQL migration manually
ALTER TABLE sessions ADD COLUMN mode VARCHAR(20) DEFAULT 'personal';
ALTER TABLE sessions ADD COLUMN user_id INTEGER;

ALTER TABLE mode_settings ADD COLUMN pii_filtering_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE mode_settings ADD COLUMN pii_redaction_config TEXT;

CREATE INDEX idx_sessions_user_mode_updated
ON sessions(user_id, mode, updated_at DESC);
```

### Using AWS Systems Manager (Parameter Store)

If storing configuration in Parameter Store:

```bash
# Store PII filtering defaults
aws ssm put-parameter \
  --name "/theo/pii/default-enabled" \
  --value "false" \
  --type String

aws ssm put-parameter \
  --name "/theo/pii/default-types" \
  --value '{"emails":true,"phones":true,"ssns":true,"creditCards":true}' \
  --type String
```

### CloudWatch Logs

Monitor the deployment:

```bash
# View backend logs
aws logs tail /aws/elasticbeanstalk/theo/backend --follow

# Filter for migration logs
aws logs filter-log-events \
  --log-group-name /aws/elasticbeanstalk/theo/backend \
  --filter-pattern "MIGRATION 003"

# Filter for PII-related logs
aws logs filter-log-events \
  --log-group-name /aws/elasticbeanstalk/theo/backend \
  --filter-pattern "[PII]"
```

---

## Quick Reference Commands

```bash
# Full deployment sequence
ssh your-ec2-instance
cd /var/app/current/backend
python3 migrations/003_add_mode_to_sessions.py
sudo systemctl restart theo-backend
curl http://localhost:1066/health

# Quick verification
sqlite3 /path/to/theo.db "SELECT COUNT(*) FROM sessions WHERE mode IS NOT NULL;"
curl http://localhost:1066/api/mode/settings/work/pii-config -H "Authorization: Bearer TOKEN"
```

---

## Support

If you encounter issues:

1. Check backend logs: `tail -f /var/log/theo/backend.log`
2. Check migration output for errors
3. Verify database schema matches expected structure
4. Test API endpoints individually
5. Check browser console for frontend errors

---

## Summary

**Required Steps**:
1. ✅ SSH into AWS instance
2. ✅ Run migration: `python3 migrations/003_add_mode_to_sessions.py`
3. ✅ Restart backend service
4. ✅ Verify endpoints working
5. ✅ Test frontend features

**Time Estimate**: 5-10 minutes
**Downtime**: ~30 seconds (during backend restart)
**Rollback Time**: <2 minutes (if backup available)

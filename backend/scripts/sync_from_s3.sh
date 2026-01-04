#!/bin/bash

# ========================================
# THEO Database Sync from AWS S3 to Unraid
# ========================================
# Downloads the latest database backup from S3 to local storage
# Designed to run on Unraid as a cron job

set -e

# Configuration
S3_BUCKET="${THEO_S3_BACKUP_BUCKET:-theo-prod-backups}"
S3_KEY="${THEO_S3_BACKUP_KEY:-theo/theo.db}"
LOCAL_DB_PATH="${LOCAL_DB_PATH:-/mnt/user/appdata/theo/data/theo.db}"
BACKUP_DIR="${BACKUP_DIR:-/mnt/user/appdata/theo/data/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================="
echo "THEO S3 Database Sync"
echo "========================================="
echo ""
echo -e "${BLUE}Source:${NC} s3://${S3_BUCKET}/${S3_KEY}"
echo -e "${BLUE}Destination:${NC} ${LOCAL_DB_PATH}"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}ERROR: AWS CLI not found${NC}"
    echo "Install with: apt-get install awscli"
    echo "Or: pip install awscli"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}ERROR: AWS credentials not configured${NC}"
    echo "Run: aws configure"
    echo "Or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables"
    exit 1
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Backup current database before overwriting (if it exists)
if [ -f "$LOCAL_DB_PATH" ]; then
    echo -e "${YELLOW}Backing up current database...${NC}"
    BACKUP_FILE="${BACKUP_DIR}/theo_pre_s3_sync_${TIMESTAMP}.db"
    cp "$LOCAL_DB_PATH" "$BACKUP_FILE"
    echo -e "${GREEN}✓ Current database backed up to: ${BACKUP_FILE}${NC}"
    echo ""
fi

# Download latest database from S3
echo -e "${BLUE}Downloading latest database from S3...${NC}"
if aws s3 cp "s3://${S3_BUCKET}/${S3_KEY}" "${LOCAL_DB_PATH}.tmp"; then
    # Verify downloaded file is a valid SQLite database
    if sqlite3 "${LOCAL_DB_PATH}.tmp" "PRAGMA integrity_check;" &> /dev/null; then
        # Move temp file to actual location
        mv "${LOCAL_DB_PATH}.tmp" "$LOCAL_DB_PATH"

        # Get file size
        DB_SIZE=$(du -h "$LOCAL_DB_PATH" | cut -f1)

        echo -e "${GREEN}✓ Database downloaded successfully${NC}"
        echo -e "${GREEN}✓ Size: ${DB_SIZE}${NC}"
        echo -e "${GREEN}✓ Integrity check passed${NC}"
        echo ""

        # Show database statistics
        echo "Database Statistics:"
        echo "-------------------"
        sqlite3 "$LOCAL_DB_PATH" << EOF
.mode column
SELECT 'Users' as table_name, COUNT(*) as row_count FROM users
UNION ALL
SELECT 'Sessions', COUNT(*) FROM sessions
UNION ALL
SELECT 'Turns', COUNT(*) FROM turns
UNION ALL
SELECT 'Memories', COUNT(*) FROM memories
UNION ALL
SELECT 'Preferences', COUNT(*) FROM preferences;
EOF
        echo ""

        # Restart THEO backend to pick up new database
        echo -e "${YELLOW}Restarting THEO backend...${NC}"
        if command -v docker-compose &> /dev/null; then
            cd /mnt/user/appdata/theo
            docker-compose restart theo-backend
            echo -e "${GREEN}✓ Backend restarted${NC}"
        else
            echo -e "${YELLOW}⚠ docker-compose not found, skipping restart${NC}"
            echo "  Manually restart: docker-compose restart theo-backend"
        fi

    else
        echo -e "${RED}✗ Downloaded file failed integrity check${NC}"
        rm -f "${LOCAL_DB_PATH}.tmp"
        exit 1
    fi
else
    echo -e "${RED}✗ Failed to download database from S3${NC}"
    rm -f "${LOCAL_DB_PATH}.tmp"
    exit 1
fi

# Cleanup old backups (keep last 7 days)
echo ""
echo "Cleaning up old backups (keeping last 7 days)..."
find "$BACKUP_DIR" -name "theo_pre_s3_sync_*.db" -mtime +7 -delete
echo -e "${GREEN}✓ Cleanup complete${NC}"

echo ""
echo "========================================="
echo -e "${GREEN}✓ Sync completed successfully!${NC}"
echo "========================================="
echo "Synced at: $(date)"
echo ""

exit 0

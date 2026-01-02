#!/bin/bash

# Database Backup Script for THEO
# Creates timestamped backups of the SQLite database with integrity verification

set -e  # Exit on error

# Configuration
DB_PATH="${DB_PATH:-data/theo.db}"
BACKUP_DIR="${BACKUP_DIR:-data/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/theo_backup_${TIMESTAMP}.db"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================================="
echo "THEO Database Backup Utility"
echo "=================================================="
echo ""

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo -e "${RED}Error: Database not found at $DB_PATH${NC}"
    exit 1
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Get database size
DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
echo "Database location: $DB_PATH"
echo "Database size: $DB_SIZE"
echo "Backup destination: $BACKUP_FILE"
echo ""

# Perform backup
echo "Creating backup..."
cp "$DB_PATH" "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Backup created successfully${NC}"
else
    echo -e "${RED}✗ Backup failed${NC}"
    exit 1
fi

# Verify backup integrity
echo ""
echo "Verifying backup integrity..."
INTEGRITY_CHECK=$(sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" 2>&1)

if [ "$INTEGRITY_CHECK" = "ok" ]; then
    echo -e "${GREEN}✓ Integrity check passed${NC}"
else
    echo -e "${RED}✗ Integrity check failed:${NC}"
    echo "$INTEGRITY_CHECK"
    exit 1
fi

# Verify backup size matches original
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo -e "${GREEN}✓ Backup size: $BACKUP_SIZE${NC}"

# Get row counts for verification
echo ""
echo "Database statistics:"
echo "-------------------"
sqlite3 "$BACKUP_FILE" << EOF
.mode column
SELECT 'Users' as table_name, COUNT(*) as row_count FROM users
UNION ALL
SELECT 'Memories', COUNT(*) FROM memories
UNION ALL
SELECT 'Preferences', COUNT(*) FROM preferences
UNION ALL
SELECT 'Intents', COUNT(*) FROM intents
UNION ALL
SELECT 'Routing Preferences', COUNT(*) FROM routing_preferences;
EOF

echo ""
echo "=================================================="
echo -e "${GREEN}Backup completed successfully!${NC}"
echo "=================================================="
echo "Backup file: $BACKUP_FILE"
echo ""
echo "To restore this backup:"
echo "  cp $BACKUP_FILE $DB_PATH"
echo ""

# List recent backups
echo "Recent backups:"
ls -lht "$BACKUP_DIR" | head -6

exit 0

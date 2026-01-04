#!/bin/bash
set -e

# Check for S3 restore file and swap databases if it exists
DATA_DIR="${THEO_DATA_DIR:-/data}"
DB_PATH="$DATA_DIR/theo.db"
RESTORE_DB_PATH="$DATA_DIR/theo_s3_restore.db"

if [ -f "$RESTORE_DB_PATH" ]; then
    echo "========================================="
    echo "S3 RESTORE DETECTED"
    echo "========================================="
    echo "Found restored database at $RESTORE_DB_PATH"

    # Backup current database if it exists
    if [ -f "$DB_PATH" ]; then
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        BACKUP_PATH="$DATA_DIR/backups/theo_pre_s3_restore_${TIMESTAMP}.db"
        mkdir -p "$DATA_DIR/backups"
        echo "Backing up current database to $BACKUP_PATH"
        cp "$DB_PATH" "$BACKUP_PATH"
        echo "Deleting old database..."
        rm -f "$DB_PATH"
    fi

    echo "Activating restored database..."
    mv "$RESTORE_DB_PATH" "$DB_PATH"
    echo "✓ Database restored successfully from S3!"
    echo "========================================="
fi

# Check if database exists
if [ -f "$DB_PATH" ]; then
    echo "Database found at $DB_PATH. Running migrations..."
    cd /app/migrations
    python run_migrations.py "$DB_PATH"
    cd /app  # Return to app directory
else
    echo "Database not found at $DB_PATH. Will be created on first application start."
    echo "Note: Run migrations manually after first start if needed."
fi

echo "Starting application..."
cd /app  # Ensure we're in the app directory
exec gunicorn -w 1 -k sync --timeout 0 --graceful-timeout 0 --keep-alive 75 -b 0.0.0.0:1066 app:app

#!/bin/bash
set -e

# Check if database exists
DB_PATH="${THEO_DATA_DIR:-/data}/theo.db"

if [ -f "$DB_PATH" ]; then
    echo "Database found at $DB_PATH. Running migrations..."
    cd /app/migrations
    python run_migrations.py "$DB_PATH"
else
    echo "Database not found at $DB_PATH. Will be created on first application start."
    echo "Note: Run migrations manually after first start if needed."
fi

echo "Starting application..."
exec gunicorn -w 1 -k sync --timeout 0 --graceful-timeout 0 --keep-alive 75 -b 0.0.0.0:1066 app:app

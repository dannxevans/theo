#!/bin/bash
set -e

# THEO Docker Entrypoint
# Runs database migrations and starts the application

DATA_DIR="${THEO_DATA_DIR:-/data}"
DB_PATH="$DATA_DIR/theo.db"

echo "========================================="
echo "THEO Application Startup"
echo "========================================="
echo "Data directory: $DATA_DIR"
echo "Database path: $DB_PATH"
echo ""

# Check if database exists
if [ -f "$DB_PATH" ]; then
    echo "Database found at $DB_PATH. Running migrations..."
    cd /app/migrations
    python run_migrations.py "$DB_PATH"
    cd /app  # Return to app directory
    echo "✓ Migrations complete"
else
    echo "Database not found at $DB_PATH."
    echo "A new database will be created on first application start."
fi

echo ""
echo "Starting application..."
echo "========================================="
cd /app  # Ensure we're in the app directory
exec gunicorn -w 1 -k sync --timeout 0 --graceful-timeout 0 --keep-alive 75 -b 0.0.0.0:1066 app:app

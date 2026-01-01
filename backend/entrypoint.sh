#!/bin/bash
set -e

echo "Running database migrations..."
cd /app/migrations
python run_migrations.py

echo "Starting application..."
exec gunicorn -w 1 -k sync --timeout 0 --graceful-timeout 0 --keep-alive 75 -b 0.0.0.0:1066 app:app

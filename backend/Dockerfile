# =============================
# THEO Backend Dockerfile
# =============================

FROM python:3.11-slim

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


# Set working directory
WORKDIR /app

# Persistent data directory for SQLite
RUN mkdir -p /data && chmod 777 /data
ENV THEO_DATA_DIR=/data

# System dependencies (minimal)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY . /app

# Expose THEO backend port
EXPOSE 1066

# Default command
CMD ["python", "app.py"]
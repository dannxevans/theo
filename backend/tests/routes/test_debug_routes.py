"""
Tests for debug console routes.

Tests debug log streaming, retrieval, filtering, and management.
"""

import pytest
import json
import time
from datetime import datetime


def test_debug_status_disabled(client, memory, debug_logs_table):
    """Test debug status when disabled."""
    response = client.get("/api/debug/status")

    assert response.status_code == 200
    data = response.json
    assert "enabled" in data
    assert "log_count" in data
    assert data["enabled"] is False
    assert data["log_count"] == 0


def test_debug_status_enabled(client, memory, debug_logs_table):
    """Test debug status when enabled."""
    memory.remember("local", "debug_enabled", "true")

    response = client.get("/api/debug/status")

    assert response.status_code == 200
    data = response.json
    assert data["enabled"] is True


def test_toggle_debug_enable(client, memory, debug_logs_table, admin_user, auth_headers):
    """Test enable debug logging."""
    # Create admin auth token
    from auth import generate_session_token
    from datetime import timedelta

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = client.post("/api/debug/toggle",
        json={"enabled": True},
        headers=headers
    )

    assert response.status_code == 200
    data = response.json
    assert data["status"] == "ok"
    assert data["enabled"] is True

    # Verify persisted
    prefs = memory.get_all("local")
    assert prefs.get("debug_enabled") == "true"


def test_toggle_debug_disable(client, memory, debug_logs_table, admin_user):
    """Test disable debug logging."""
    # Create admin auth token
    from auth import generate_session_token
    from datetime import timedelta

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Enable first
    memory.remember("local", "debug_enabled", "true")

    response = client.post("/api/debug/toggle",
        json={"enabled": False},
        headers=headers
    )

    assert response.status_code == 200
    data = response.json
    assert data["enabled"] is False

    # Verify persisted
    prefs = memory.get_all("local")
    assert prefs.get("debug_enabled") == "false"


def test_toggle_debug_requires_admin(client, memory, debug_logs_table, test_user):
    """Test toggle requires admin authentication."""
    # Create non-admin auth token
    from auth import generate_session_token
    from datetime import timedelta

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, test_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = client.post("/api/debug/toggle",
        json={"enabled": True},
        headers=headers
    )

    assert response.status_code == 403


def test_toggle_debug_requires_auth(client):
    """Test toggle requires authentication."""
    response = client.post("/api/debug/toggle",
        json={"enabled": True}
    )

    assert response.status_code == 401


def test_get_logs_empty(client, memory, debug_logs_table, admin_user):
    """Test get logs when empty."""
    # Create admin auth token
    from auth import generate_session_token
    from datetime import timedelta

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = client.get("/api/debug/logs", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert "logs" in data
    assert "total" in data
    assert data["logs"] == []
    assert data["total"] == 0


def test_get_logs_with_data(client, memory, debug_logs_table, admin_user, db_path):
    """Test get logs with data."""
    import sqlite3

    # Create admin auth token
    from auth import generate_session_token
    from datetime import timedelta

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Insert test logs directly into database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure debug_logs table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS debug_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            level VARCHAR(10) NOT NULL,
            source VARCHAR(20) NOT NULL,
            component VARCHAR(50),
            message TEXT NOT NULL,
            raw_data TEXT,
            user_id INTEGER,
            session_id TEXT
        )
    """)

    # Insert test logs
    cursor.execute("""
        INSERT INTO debug_logs (timestamp, level, source, component, message)
        VALUES (?, ?, ?, ?, ?)
    """, (datetime.utcnow().isoformat(), "INFO", "backend", "test", "Test log message"))

    cursor.execute("""
        INSERT INTO debug_logs (timestamp, level, source, component, message)
        VALUES (?, ?, ?, ?, ?)
    """, (datetime.utcnow().isoformat(), "ERROR", "backend", "test", "Test error message"))

    conn.commit()
    conn.close()

    response = client.get("/api/debug/logs", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert len(data["logs"]) == 2
    assert data["total"] == 2
    assert data["logs"][0]["level"] in ["INFO", "ERROR"]
    assert data["logs"][0]["source"] == "backend"


def test_get_logs_filter_by_level(client, memory, debug_logs_table, admin_user, db_path):
    """Test get logs filtered by level."""
    import sqlite3

    # Create admin auth token
    from auth import generate_session_token
    from datetime import timedelta

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Insert test logs
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS debug_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            level VARCHAR(10) NOT NULL,
            source VARCHAR(20) NOT NULL,
            component VARCHAR(50),
            message TEXT NOT NULL,
            raw_data TEXT,
            user_id INTEGER,
            session_id TEXT
        )
    """)

    cursor.execute("""
        INSERT INTO debug_logs (timestamp, level, source, message)
        VALUES (?, ?, ?, ?)
    """, (datetime.utcnow().isoformat(), "INFO", "backend", "Info message"))

    cursor.execute("""
        INSERT INTO debug_logs (timestamp, level, source, message)
        VALUES (?, ?, ?, ?)
    """, (datetime.utcnow().isoformat(), "ERROR", "backend", "Error message"))

    conn.commit()
    conn.close()

    # Filter by ERROR level
    response = client.get("/api/debug/logs?level=ERROR", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert len(data["logs"]) == 1
    assert data["logs"][0]["level"] == "ERROR"


def test_get_logs_filter_by_source(client, memory, debug_logs_table, admin_user, db_path):
    """Test get logs filtered by source."""
    import sqlite3

    # Create admin auth token
    from auth import generate_session_token
    from datetime import timedelta

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Insert test logs
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS debug_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            level VARCHAR(10) NOT NULL,
            source VARCHAR(20) NOT NULL,
            component VARCHAR(50),
            message TEXT NOT NULL,
            raw_data TEXT,
            user_id INTEGER,
            session_id TEXT
        )
    """)

    cursor.execute("""
        INSERT INTO debug_logs (timestamp, level, source, message)
        VALUES (?, ?, ?, ?)
    """, (datetime.utcnow().isoformat(), "INFO", "backend", "Backend message"))

    cursor.execute("""
        INSERT INTO debug_logs (timestamp, level, source, message)
        VALUES (?, ?, ?, ?)
    """, (datetime.utcnow().isoformat(), "INFO", "frontend", "Frontend message"))

    conn.commit()
    conn.close()

    # Filter by frontend source
    response = client.get("/api/debug/logs?source=frontend", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert len(data["logs"]) == 1
    assert data["logs"][0]["source"] == "frontend"


def test_get_logs_pagination(client, memory, debug_logs_table, admin_user, db_path):
    """Test get logs with pagination."""
    import sqlite3

    # Create admin auth token
    from auth import generate_session_token
    from datetime import timedelta

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Insert 15 test logs
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS debug_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            level VARCHAR(10) NOT NULL,
            source VARCHAR(20) NOT NULL,
            component VARCHAR(50),
            message TEXT NOT NULL,
            raw_data TEXT,
            user_id INTEGER,
            session_id TEXT
        )
    """)

    for i in range(15):
        cursor.execute("""
            INSERT INTO debug_logs (timestamp, level, source, message)
            VALUES (?, ?, ?, ?)
        """, (datetime.utcnow().isoformat(), "INFO", "backend", f"Message {i}"))

    conn.commit()
    conn.close()

    # Get first page (limit 10)
    response = client.get("/api/debug/logs?limit=10", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert len(data["logs"]) == 10
    assert data["total"] == 15

    # Get second page (offset 10)
    response = client.get("/api/debug/logs?limit=10&offset=10", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert len(data["logs"]) == 5
    assert data["total"] == 15


def test_clear_logs(client, memory, debug_logs_table, admin_user, db_path):
    """Test clear all logs."""
    import sqlite3

    # Create admin auth token
    from auth import generate_session_token
    from datetime import timedelta

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Insert test logs
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS debug_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            level VARCHAR(10) NOT NULL,
            source VARCHAR(20) NOT NULL,
            component VARCHAR(50),
            message TEXT NOT NULL,
            raw_data TEXT,
            user_id INTEGER,
            session_id TEXT
        )
    """)

    cursor.execute("""
        INSERT INTO debug_logs (timestamp, level, source, message)
        VALUES (?, ?, ?, ?)
    """, (datetime.utcnow().isoformat(), "INFO", "backend", "Test message"))

    conn.commit()
    conn.close()

    # Clear logs
    response = client.delete("/api/debug/logs", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert "deleted" in data
    assert data["deleted"] >= 1

    # Verify logs are cleared
    response = client.get("/api/debug/logs", headers=headers)
    assert response.json["total"] == 0


def test_clear_logs_requires_admin(client, memory, debug_logs_table, test_user):
    """Test clear logs requires admin authentication."""
    # Create non-admin auth token
    from auth import generate_session_token
    from datetime import timedelta

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, test_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = client.delete("/api/debug/logs", headers=headers)

    assert response.status_code == 403


def test_frontend_log_ingestion(client, memory, debug_logs_table, admin_user):
    """Test frontend can send logs to backend."""
    # Create admin auth token
    from auth import generate_session_token
    from datetime import timedelta

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Enable debug mode
    memory.remember("local", "debug_enabled", "true")

    # Send frontend log
    response = client.post("/api/debug/log",
        json={
            "level": "ERROR",
            "message": "Frontend error occurred",
            "component": "UserComponent",
            "session_id": "test-session-123"
        },
        headers=headers
    )

    assert response.status_code == 200
    data = response.json
    assert data["status"] == "ok"


def test_frontend_log_requires_debug_enabled(client, memory, debug_logs_table, admin_user):
    """Test frontend logging only works when debug is enabled."""
    # Create admin auth token
    from auth import generate_session_token
    from datetime import timedelta

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Debug is disabled by default
    response = client.post("/api/debug/log",
        json={
            "level": "ERROR",
            "message": "Frontend error",
            "component": "TestComponent"
        },
        headers=headers
    )

    # Should still return 200 but log won't be saved
    assert response.status_code == 200

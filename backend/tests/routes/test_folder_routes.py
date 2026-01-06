"""
Tests for folder API routes.

Tests folder management endpoints including CRUD operations,
session movement, archiving, and state management.
"""

import pytest
import json


def test_get_folders(client, auth_headers, test_user):
    """Test GET /api/folders endpoint."""
    response = client.get("/api/folders", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)
    assert len(data) >= 1  # At least Archive folder
    assert data[0]["name"] == "Archive"
    assert data[0]["is_system"] == True


def test_get_folders_unauthorized(client):
    """Test GET /api/folders without authentication."""
    response = client.get("/api/folders")
    assert response.status_code == 401


def test_create_folder(client, auth_headers):
    """Test POST /api/folders endpoint."""
    response = client.post(
        "/api/folders",
        headers=auth_headers,
        json={"name": "Work Projects"}
    )

    assert response.status_code == 201
    data = response.json
    assert data["name"] == "Work Projects"
    assert data["is_system"] == False
    assert data["collapsed"] == False


def test_create_folder_missing_name(client, auth_headers):
    """Test POST /api/folders without name."""
    response = client.post(
        "/api/folders",
        headers=auth_headers,
        json={}
    )

    assert response.status_code == 400
    assert "error" in response.json


def test_create_folder_name_too_long(client, auth_headers):
    """Test POST /api/folders with name > 100 chars."""
    response = client.post(
        "/api/folders",
        headers=auth_headers,
        json={"name": "X" * 101}
    )

    assert response.status_code == 400
    assert "error" in response.json


def test_create_folder_duplicate_name(client, auth_headers):
    """Test creating folder with duplicate name."""
    # Create first folder
    client.post(
        "/api/folders",
        headers=auth_headers,
        json={"name": "Projects"}
    )

    # Try to create duplicate
    response = client.post(
        "/api/folders",
        headers=auth_headers,
        json={"name": "Projects"}
    )

    assert response.status_code == 400
    assert "error" in response.json


def test_rename_folder(client, auth_headers, memory, test_user):
    """Test PUT /api/folders/:id to rename."""
    # Create folder
    folder = memory.create_folder(test_user["id"], "Old Name")
    folder_id = folder["id"]

    # Rename it
    response = client.put(
        f"/api/folders/{folder_id}",
        headers=auth_headers,
        json={"name": "New Name"}
    )

    assert response.status_code == 200
    assert response.json["success"] == True

    # Verify rename
    folders = memory.get_folders(test_user["id"])
    renamed = next((f for f in folders if f["id"] == folder_id), None)
    assert renamed["name"] == "New Name"


def test_rename_folder_invalid_name(client, auth_headers, memory, test_user):
    """Test PUT /api/folders/:id with invalid name."""
    folder = memory.create_folder(test_user["id"], "Test Folder")
    folder_id = folder["id"]

    # Too long
    response = client.put(
        f"/api/folders/{folder_id}",
        headers=auth_headers,
        json={"name": "X" * 101}
    )
    assert response.status_code == 400

    # Empty
    response = client.put(
        f"/api/folders/{folder_id}",
        headers=auth_headers,
        json={"name": ""}
    )
    assert response.status_code == 400


def test_rename_system_folder_fails(client, auth_headers, memory, test_user):
    """Test that system folders cannot be renamed."""
    archive_id = memory.get_archive_folder_id(test_user["id"])

    response = client.put(
        f"/api/folders/{archive_id}",
        headers=auth_headers,
        json={"name": "Hacked Archive"}
    )

    assert response.status_code == 400
    assert "error" in response.json


def test_update_folder_collapsed(client, auth_headers, memory, test_user):
    """Test PUT /api/folders/:id to toggle collapsed state."""
    folder = memory.create_folder(test_user["id"], "My Folder")
    folder_id = folder["id"]

    # Collapse it
    response = client.put(
        f"/api/folders/{folder_id}",
        headers=auth_headers,
        json={"collapsed": True}
    )

    assert response.status_code == 200
    assert response.json["success"] == True

    # Verify state
    updated = memory.get_folder_by_id(folder_id, test_user["id"])
    assert updated["collapsed"] == True


def test_update_folder_collapsed_invalid_type(client, auth_headers, memory, test_user):
    """Test PUT /api/folders/:id with invalid collapsed value."""
    folder = memory.create_folder(test_user["id"], "My Folder")
    folder_id = folder["id"]

    response = client.put(
        f"/api/folders/{folder_id}",
        headers=auth_headers,
        json={"collapsed": "not a boolean"}
    )

    assert response.status_code == 400


def test_delete_folder(client, auth_headers, memory, test_user):
    """Test DELETE /api/folders/:id endpoint."""
    folder = memory.create_folder(test_user["id"], "Temp Folder")
    folder_id = folder["id"]

    response = client.delete(
        f"/api/folders/{folder_id}",
        headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json["success"] == True

    # Verify deleted
    folders = memory.get_folders(test_user["id"])
    assert not any(f["id"] == folder_id for f in folders)


def test_delete_system_folder_fails(client, auth_headers, memory, test_user):
    """Test that system folders cannot be deleted."""
    archive_id = memory.get_archive_folder_id(test_user["id"])

    response = client.delete(
        f"/api/folders/{archive_id}",
        headers=auth_headers
    )

    assert response.status_code == 400
    assert "error" in response.json


def test_move_session_to_folder(client, auth_headers, memory, test_user):
    """Test POST /api/sessions/:id/move endpoint."""
    # Create folder and session
    folder = memory.create_folder(test_user["id"], "Projects")
    folder_id = folder["id"]

    memory.save_turn("session-123", "user", "Hello", user_id=test_user["id"])

    # Move session
    response = client.post(
        "/api/sessions/session-123/move",
        headers=auth_headers,
        json={"folder_id": folder_id}
    )

    assert response.status_code == 200
    assert response.json["success"] == True

    # Verify moved
    sessions = memory.list_sessions(user_id=test_user["id"])
    session = next((s for s in sessions if s["id"] == "session-123"), None)
    assert session["folder_id"] == folder_id


def test_move_session_to_unfiled(client, auth_headers, memory, test_user):
    """Test moving session to unfiled (folder_id=null)."""
    # Create folder and session
    folder = memory.create_folder(test_user["id"], "Projects")
    memory.save_turn("session-123", "user", "Hello", user_id=test_user["id"])
    memory.move_session_to_folder("session-123", folder["id"], test_user["id"])

    # Move to unfiled
    response = client.post(
        "/api/sessions/session-123/move",
        headers=auth_headers,
        json={"folder_id": None}
    )

    assert response.status_code == 200
    assert response.json["success"] == True

    # Verify unfiled
    sessions = memory.list_sessions(user_id=test_user["id"])
    session = next((s for s in sessions if s["id"] == "session-123"), None)
    assert session["folder_id"] is None


def test_move_session_to_nonexistent_folder(client, auth_headers, memory, test_user):
    """Test moving session to nonexistent folder fails."""
    memory.save_turn("session-123", "user", "Hello", user_id=test_user["id"])

    response = client.post(
        "/api/sessions/session-123/move",
        headers=auth_headers,
        json={"folder_id": 999999}
    )

    assert response.status_code == 400
    assert "error" in response.json


def test_archive_session(client, auth_headers, memory, test_user):
    """Test POST /api/sessions/:id/archive endpoint."""
    memory.save_turn("session-archive", "user", "Old chat", user_id=test_user["id"])

    response = client.post(
        "/api/sessions/session-archive/archive",
        headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json["success"] == True

    # Verify archived
    archive_id = memory.get_archive_folder_id(test_user["id"])
    sessions = memory.list_sessions(user_id=test_user["id"])
    session = next((s for s in sessions if s["id"] == "session-archive"), None)
    assert session["folder_id"] == archive_id


def test_reorder_folders(client, auth_headers, memory, test_user):
    """Test POST /api/folders/reorder endpoint."""
    # Create folders
    folder1 = memory.create_folder(test_user["id"], "Folder A")
    folder2 = memory.create_folder(test_user["id"], "Folder B")
    folder3 = memory.create_folder(test_user["id"], "Folder C")

    # Reorder: C, A, B
    new_order = [folder3["id"], folder1["id"], folder2["id"]]
    response = client.post(
        "/api/folders/reorder",
        headers=auth_headers,
        json={"folder_order": new_order}
    )

    assert response.status_code == 200
    assert response.json["success"] == True

    # Verify order
    folders = memory.get_folders(test_user["id"])
    custom_folders = [f for f in folders if not f["is_system"]]
    assert custom_folders[0]["id"] == folder3["id"]
    assert custom_folders[1]["id"] == folder1["id"]
    assert custom_folders[2]["id"] == folder2["id"]


def test_reorder_folders_invalid_input(client, auth_headers):
    """Test POST /api/folders/reorder with invalid input."""
    response = client.post(
        "/api/folders/reorder",
        headers=auth_headers,
        json={"folder_order": "not an array"}
    )

    assert response.status_code == 400
    assert "error" in response.json


def test_folder_operations_require_auth(client):
    """Test that all folder endpoints require authentication."""
    # No auth headers
    endpoints = [
        ("GET", "/api/folders"),
        ("POST", "/api/folders", {"name": "Test"}),
        ("PUT", "/api/folders/1", {"name": "Test"}),
        ("DELETE", "/api/folders/1"),
        ("POST", "/api/sessions/test/move", {"folder_id": 1}),
        ("POST", "/api/sessions/test/archive"),
        ("POST", "/api/folders/reorder", {"folder_order": []}),
    ]

    for method, url, *args in endpoints:
        data = args[0] if args else None
        if method == "GET":
            response = client.get(url)
        elif method == "POST":
            response = client.post(url, json=data)
        elif method == "PUT":
            response = client.put(url, json=data)
        elif method == "DELETE":
            response = client.delete(url)

        assert response.status_code == 401, f"{method} {url} should require auth"


def test_sessions_list_includes_folder_info(client, auth_headers, memory, test_user):
    """Test that /api/sessions includes folder_id and folder_name."""
    # Create folder and session
    folder = memory.create_folder(test_user["id"], "My Projects")
    memory.save_turn("session-in-folder", "user", "Hello", user_id=test_user["id"])
    memory.move_session_to_folder("session-in-folder", folder["id"], test_user["id"])

    # List sessions
    response = client.get("/api/sessions")
    assert response.status_code == 200

    sessions = response.json
    session = next((s for s in sessions if s["id"] == "session-in-folder"), None)
    assert session is not None
    assert session["folder_id"] == folder["id"]
    assert session["folder_name"] == "My Projects"


def test_delete_folder_moves_sessions_to_unfiled(client, auth_headers, memory, test_user):
    """Test that deleting a folder moves its sessions to unfiled."""
    # Create folder and session
    folder = memory.create_folder(test_user["id"], "Temp")
    memory.save_turn("session-1", "user", "Test", user_id=test_user["id"])
    memory.move_session_to_folder("session-1", folder["id"], test_user["id"])

    # Delete folder
    response = client.delete(f"/api/folders/{folder['id']}", headers=auth_headers)
    assert response.status_code == 200

    # Verify session is unfiled
    sessions = memory.list_sessions(user_id=test_user["id"])
    session = next((s for s in sessions if s["id"] == "session-1"), None)
    assert session["folder_id"] is None


@pytest.mark.skip(reason="Folder ownership validation tested at memory layer in test_folders.py::test_folder_ownership_validation")
def test_folder_isolation_between_users(client, memory):
    """Test that users can only access their own folders."""
    from auth import hash_password, generate_session_token
    from datetime import datetime, timedelta

    # Create two users
    password_hash = hash_password("pass123")
    user1_id = memory.create_user("user1", password_hash, is_admin=False)
    user2_id = memory.create_user("user2", password_hash, is_admin=False)

    # User1 creates folder
    folder1 = memory.create_folder(user1_id, "User1 Private")

    # Create auth for user2
    token2 = generate_session_token()
    memory.create_auth_session(token2, user2_id, datetime.utcnow() + timedelta(days=1))
    headers2 = {"Authorization": f"Bearer {token2}", "Content-Type": "application/json"}

    # User2 tries to rename User1's folder - should fail
    response = client.put(
        f"/api/folders/{folder1['id']}",
        headers=headers2,
        json={"name": "Stolen"}
    )
    assert response.status_code == 400

    # User2 tries to delete User1's folder - should fail
    response = client.delete(
        f"/api/folders/{folder1['id']}",
        headers=headers2
    )
    assert response.status_code == 400

    # User2 shouldn't see User1's folder in list
    response = client.get("/api/folders", headers=headers2)
    user2_folders = response.json
    assert not any(f["id"] == folder1["id"] for f in user2_folders)

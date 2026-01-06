"""
Tests for folder operations.

Tests folder CRUD, session organization, archiving, and state management.
"""

import pytest
from datetime import datetime


def test_create_folder(memory, user_fixture):
    """Test creating a custom folder."""
    user_id = user_fixture["id"]

    folder = memory.create_folder(user_id, "Work Projects")

    assert folder is not None
    assert folder["name"] == "Work Projects"
    assert folder["user_id"] == user_id
    assert folder["is_system"] == False
    assert folder["collapsed"] == False


def test_create_folder_invalid_name(memory, user_fixture):
    """Test creating folder with invalid name."""
    user_id = user_fixture["id"]

    # Empty name
    folder = memory.create_folder(user_id, "")
    assert folder is None

    # Too long (over 100 chars)
    folder = memory.create_folder(user_id, "X" * 101)
    assert folder is None


def test_get_folders_archive_first(memory, user_fixture):
    """Test that Archive folder is always first in list."""
    user_id = user_fixture["id"]

    # Create some custom folders
    memory.create_folder(user_id, "AAA First Alphabetically")
    memory.create_folder(user_id, "Projects")

    folders = memory.get_folders(user_id)

    assert len(folders) >= 3  # At least Archive + 2 custom
    assert folders[0]["name"] == "Archive"
    assert folders[0]["is_system"] == True


def test_get_folders_empty_for_new_user(memory):
    """Test getting folders for user with no custom folders."""
    from auth import hash_password

    # Create user
    user_id = memory.create_user("newuser", hash_password("pass"), is_admin=False)

    folders = memory.get_folders(user_id)

    # Should have Archive folder auto-created by migration
    assert len(folders) == 1
    assert folders[0]["name"] == "Archive"
    assert folders[0]["is_system"] == True


def test_rename_folder(memory, user_fixture):
    """Test renaming a custom folder."""
    user_id = user_fixture["id"]

    folder = memory.create_folder(user_id, "Old Name")
    folder_id = folder["id"]

    success = memory.rename_folder(folder_id, user_id, "New Name")
    assert success == True

    folders = memory.get_folders(user_id)
    renamed = next((f for f in folders if f["id"] == folder_id), None)
    assert renamed is not None
    assert renamed["name"] == "New Name"


def test_rename_system_folder_fails(memory, user_fixture):
    """Test that system folders cannot be renamed."""
    user_id = user_fixture["id"]

    # Get Archive folder ID
    archive_id = memory.get_archive_folder_id(user_id)
    assert archive_id is not None

    # Try to rename - should fail
    success = memory.rename_folder(archive_id, user_id, "Hacked Archive")
    assert success == False

    # Verify name unchanged
    folders = memory.get_folders(user_id)
    archive = next((f for f in folders if f["id"] == archive_id), None)
    assert archive["name"] == "Archive"


def test_delete_folder(memory, user_fixture):
    """Test deleting a custom folder."""
    user_id = user_fixture["id"]

    folder = memory.create_folder(user_id, "Temporary Folder")
    folder_id = folder["id"]

    # Create a session in the folder
    memory.save_turn("test-session", "user", "Hello", user_id=user_id)
    memory.move_session_to_folder("test-session", folder_id, user_id)

    # Delete folder
    success = memory.delete_folder(folder_id, user_id)
    assert success == True

    # Verify folder is gone
    folders = memory.get_folders(user_id)
    assert not any(f["id"] == folder_id for f in folders)

    # Verify session was unfiled
    sessions = memory.list_sessions(user_id=user_id)
    session = next((s for s in sessions if s["id"] == "test-session"), None)
    assert session is not None
    assert session["folder_id"] is None


def test_delete_system_folder_fails(memory, user_fixture):
    """Test that system folders cannot be deleted."""
    user_id = user_fixture["id"]

    archive_id = memory.get_archive_folder_id(user_id)
    assert archive_id is not None

    success = memory.delete_folder(archive_id, user_id)
    assert success == False

    # Verify Archive still exists
    folders = memory.get_folders(user_id)
    assert any(f["name"] == "Archive" for f in folders)


def test_update_folder_collapsed(memory, user_fixture):
    """Test toggling folder collapsed state."""
    user_id = user_fixture["id"]

    folder = memory.create_folder(user_id, "My Folder")
    folder_id = folder["id"]

    # Folder starts expanded (collapsed=False)
    assert folder["collapsed"] == False

    # Collapse it
    success = memory.update_folder_collapsed(folder_id, user_id, True)
    assert success == True

    folders = memory.get_folders(user_id)
    updated = next((f for f in folders if f["id"] == folder_id), None)
    assert updated["collapsed"] == True

    # Expand it again
    success = memory.update_folder_collapsed(folder_id, user_id, False)
    assert success == True

    folders = memory.get_folders(user_id)
    updated = next((f for f in folders if f["id"] == folder_id), None)
    assert updated["collapsed"] == False


def test_move_session_to_folder(memory, user_fixture):
    """Test moving a session to a folder."""
    user_id = user_fixture["id"]

    folder = memory.create_folder(user_id, "Projects")
    folder_id = folder["id"]

    # Create a session
    memory.save_turn("session-123", "user", "Hello", user_id=user_id)

    # Move to folder
    success = memory.move_session_to_folder("session-123", folder_id, user_id)
    assert success == True

    # Verify session is in folder
    sessions = memory.list_sessions(user_id=user_id)
    session = next((s for s in sessions if s["id"] == "session-123"), None)
    assert session is not None
    assert session["folder_id"] == folder_id
    assert session["folder_name"] == "Projects"


def test_move_session_to_unfiled(memory, user_fixture):
    """Test moving a session to unfiled (folder_id=None)."""
    user_id = user_fixture["id"]

    folder = memory.create_folder(user_id, "Projects")
    folder_id = folder["id"]

    # Create session in folder
    memory.save_turn("session-123", "user", "Hello", user_id=user_id)
    memory.move_session_to_folder("session-123", folder_id, user_id)

    # Move to unfiled
    success = memory.move_session_to_folder("session-123", None, user_id)
    assert success == True

    # Verify session is unfiled
    sessions = memory.list_sessions(user_id=user_id)
    session = next((s for s in sessions if s["id"] == "session-123"), None)
    assert session is not None
    assert session["folder_id"] is None
    assert session["folder_name"] is None


def test_archive_session(memory, user_fixture):
    """Test archiving a session."""
    user_id = user_fixture["id"]

    # Create session
    memory.save_turn("session-archive", "user", "Old conversation", user_id=user_id)

    # Archive it
    success = memory.archive_session("session-archive", user_id)
    assert success == True

    # Verify session is in Archive
    archive_id = memory.get_archive_folder_id(user_id)
    sessions = memory.list_sessions(user_id=user_id)
    session = next((s for s in sessions if s["id"] == "session-archive"), None)
    assert session is not None
    assert session["folder_id"] == archive_id
    assert session["folder_name"] == "Archive"


def test_get_archive_folder_id(memory, user_fixture):
    """Test getting Archive folder ID."""
    user_id = user_fixture["id"]

    archive_id = memory.get_archive_folder_id(user_id)
    assert archive_id is not None

    # Verify it's the Archive folder
    folder = memory.get_folder_by_id(archive_id, user_id)
    assert folder is not None
    assert folder["name"] == "Archive"
    assert folder["is_system"] == True


def test_folder_ownership_validation(memory, user_fixture):
    """Test that users can only modify their own folders."""
    from auth import hash_password

    user1_id = user_fixture["id"]
    user2_id = memory.create_user("user2", hash_password("pass2"), is_admin=False)

    # User1 creates folder
    folder = memory.create_folder(user1_id, "User1 Folder")
    folder_id = folder["id"]

    # User2 tries to rename - should fail
    success = memory.rename_folder(folder_id, user2_id, "Stolen Folder")
    assert success == False

    # Verify name unchanged
    folder_check = memory.get_folder_by_id(folder_id, user1_id)
    assert folder_check["name"] == "User1 Folder"

    # User2 tries to delete - should fail
    success = memory.delete_folder(folder_id, user2_id)
    assert success == False

    # Verify folder still exists
    folders = memory.get_folders(user1_id)
    assert any(f["id"] == folder_id for f in folders)


def test_reorder_folders(memory, user_fixture):
    """Test reordering custom folders."""
    user_id = user_fixture["id"]

    # Create folders
    folder1 = memory.create_folder(user_id, "Folder A")
    folder2 = memory.create_folder(user_id, "Folder B")
    folder3 = memory.create_folder(user_id, "Folder C")

    # Reorder: C, A, B
    new_order = [folder3["id"], folder1["id"], folder2["id"]]
    success = memory.reorder_folders(user_id, new_order)
    assert success == True

    # Verify order (Archive should still be first)
    folders = memory.get_folders(user_id)
    custom_folders = [f for f in folders if not f["is_system"]]

    assert custom_folders[0]["id"] == folder3["id"]
    assert custom_folders[1]["id"] == folder1["id"]
    assert custom_folders[2]["id"] == folder2["id"]


def test_sessions_list_includes_folder_info(memory, user_fixture):
    """Test that list_sessions includes folder_id and folder_name."""
    user_id = user_fixture["id"]

    folder = memory.create_folder(user_id, "My Projects")
    folder_id = folder["id"]

    # Create sessions
    memory.save_turn("session-in-folder", "user", "Hello", user_id=user_id)
    memory.save_turn("session-unfiled", "user", "Hi", user_id=user_id)

    # Move one to folder
    memory.move_session_to_folder("session-in-folder", folder_id, user_id)

    # List sessions
    sessions = memory.list_sessions(user_id=user_id)

    in_folder = next((s for s in sessions if s["id"] == "session-in-folder"), None)
    assert in_folder is not None
    assert in_folder["folder_id"] == folder_id
    assert in_folder["folder_name"] == "My Projects"

    unfiled = next((s for s in sessions if s["id"] == "session-unfiled"), None)
    assert unfiled is not None
    assert unfiled["folder_id"] is None
    assert unfiled["folder_name"] is None


def test_duplicate_folder_names_same_user(memory, user_fixture):
    """Test that duplicate folder names for same user are prevented."""
    user_id = user_fixture["id"]

    # Create folder
    folder1 = memory.create_folder(user_id, "Projects")
    assert folder1 is not None

    # Try to create duplicate - should fail
    folder2 = memory.create_folder(user_id, "Projects")
    assert folder2 is None


def test_duplicate_folder_names_different_users(memory):
    """Test that different users can have folders with same name."""
    from auth import hash_password

    user1_id = memory.create_user("user1", hash_password("pass1"), is_admin=False)
    user2_id = memory.create_user("user2", hash_password("pass2"), is_admin=False)

    # Both create "Projects" folder
    folder1 = memory.create_folder(user1_id, "Projects")
    folder2 = memory.create_folder(user2_id, "Projects")

    assert folder1 is not None
    assert folder2 is not None
    assert folder1["id"] != folder2["id"]

    # Each user sees only their own folder
    user1_folders = memory.get_folders(user1_id)
    user2_folders = memory.get_folders(user2_id)

    assert any(f["name"] == "Projects" and f["id"] == folder1["id"] for f in user1_folders)
    assert any(f["name"] == "Projects" and f["id"] == folder2["id"] for f in user2_folders)


def test_folder_isolation_between_users(memory):
    """Test that users cannot access other users' folders."""
    from auth import hash_password

    user1_id = memory.create_user("user1", hash_password("pass1"), is_admin=False)
    user2_id = memory.create_user("user2", hash_password("pass2"), is_admin=False)

    # User1 creates folder
    folder1 = memory.create_folder(user1_id, "User1 Private")

    # User2 tries to get User1's folder
    folder_check = memory.get_folder_by_id(folder1["id"], user2_id)
    assert folder_check is None


def test_move_session_to_nonexistent_folder(memory, user_fixture):
    """Test that moving to nonexistent folder fails."""
    user_id = user_fixture["id"]

    memory.save_turn("session-123", "user", "Hello", user_id=user_id)

    # Try to move to nonexistent folder ID
    success = memory.move_session_to_folder("session-123", 999999, user_id)
    assert success == False


def test_archive_folder_created_on_user_creation(memory):
    """Test that Archive folder is created when user is created."""
    from auth import hash_password

    # Create new user
    user_id = memory.create_user("newuser", hash_password("testpass"), is_admin=False)

    # Check Archive folder exists
    folders = memory.get_folders(user_id)
    archive_folders = [f for f in folders if f["is_system"] and f["name"] == "Archive"]

    assert len(archive_folders) == 1
    assert archive_folders[0]["sort_order"] == -1  # Always at top

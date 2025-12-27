"""
Tests for Phase 5: Confirmation Workflow

Tests:
1. ConfirmationManager initialization
2. Creating confirmation requests
3. Approving confirmations
4. Rejecting confirmations
5. Expired confirmations
6. End-to-end confirmation flow
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.confirmation_manager import ConfirmationManager
from core.action_router import ActionRouter
from actions.action_registry import ActionProviderRegistry
from core.memory import MemoryStore


def test_confirmation_manager_initialization():
    """Test that ConfirmationManager can be initialized."""
    print("\n=== Test 1: ConfirmationManager Initialization ===")

    try:
        # Create temporary database
        db_path = "/tmp/test_confirmation_init.db"
        if os.path.exists(db_path):
            os.remove(db_path)

        memory = MemoryStore(f"sqlite:///{db_path}")
        action_registry = ActionProviderRegistry(memory)
        action_router = ActionRouter(action_registry, memory)
        confirmation_manager = ConfirmationManager(memory, action_router)

        print("✓ ConfirmationManager initialized successfully")
        print(f"  - Manager: {confirmation_manager}")
        print(f"  - Memory: {confirmation_manager.memory}")
        print(f"  - Router: {confirmation_manager.action_router}")

        # Cleanup
        os.remove(db_path)

        return True

    except Exception as e:
        print(f"✗ Failed to initialize ConfirmationManager: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_create_confirmation():
    """Test creating a confirmation request."""
    print("\n=== Test 2: Create Confirmation Request ===")

    try:
        # Create temporary database
        db_path = "/tmp/test_create_confirmation.db"
        if os.path.exists(db_path):
            os.remove(db_path)

        memory = MemoryStore(f"sqlite:///{db_path}")
        action_registry = ActionProviderRegistry(memory)
        action_router = ActionRouter(action_registry, memory)
        confirmation_manager = ConfirmationManager(memory, action_router)

        # Create confirmation
        confirmation = confirmation_manager.create_confirmation(
            user_id=1,
            session_id="test_session",
            action_type="create_calendar_event",
            action_params={
                "subject": "Haircut",
                "start_time": "2025-12-31T17:00:00",
                "end_time": "2025-12-31T17:30:00",
                "location": "Cuts Barber"
            },
            confirmation_message="Book haircut at Cuts Barber on Dec 31 at 5:00 PM?",
            provider_id=None,
            expires_in_hours=24
        )

        print("✓ Confirmation created successfully")
        print(f"  - Confirmation ID: {confirmation['confirmation_id']}")
        print(f"  - Action ID: {confirmation['action_id']}")
        print(f"  - Message: {confirmation['message']}")
        print(f"  - Status: {confirmation['status']}")
        print(f"  - Expires at: {confirmation['expires_at']}")

        # Verify confirmation exists in database
        pending = confirmation_manager.get_pending_confirmations(user_id=1)
        if len(pending) == 1:
            print(f"✓ Found {len(pending)} pending confirmation")
        else:
            print(f"✗ Expected 1 pending confirmation, found {len(pending)}")
            return False

        # Cleanup
        os.remove(db_path)

        return True

    except Exception as e:
        print(f"✗ Failed to create confirmation: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_reject_confirmation():
    """Test rejecting a confirmation."""
    print("\n=== Test 3: Reject Confirmation ===")

    try:
        # Create temporary database
        db_path = "/tmp/test_reject_confirmation.db"
        if os.path.exists(db_path):
            os.remove(db_path)

        memory = MemoryStore(f"sqlite:///{db_path}")
        action_registry = ActionProviderRegistry(memory)
        action_router = ActionRouter(action_registry, memory)
        confirmation_manager = ConfirmationManager(memory, action_router)

        # Create confirmation
        confirmation = confirmation_manager.create_confirmation(
            user_id=1,
            session_id="test_session",
            action_type="create_calendar_event",
            action_params={"subject": "Test Event"},
            confirmation_message="Create test event?",
        )

        confirmation_id = confirmation["confirmation_id"]

        # Reject confirmation
        result = confirmation_manager.reject_confirmation(
            confirmation_id=confirmation_id,
            user_id=1,
            reason="Changed my mind"
        )

        print("✓ Confirmation rejected successfully")
        print(f"  - Status: {result['status']}")
        print(f"  - Message: {result['message']}")

        # Verify no more pending confirmations
        pending = confirmation_manager.get_pending_confirmations(user_id=1)
        if len(pending) == 0:
            print(f"✓ No pending confirmations remaining")
        else:
            print(f"✗ Expected 0 pending confirmations, found {len(pending)}")
            return False

        # Verify action status is cancelled
        action = memory.get_action_by_id(confirmation["action_id"])
        if action["status"] == "cancelled":
            print(f"✓ Action marked as cancelled")
        else:
            print(f"✗ Action status is {action['status']}, expected 'cancelled'")
            return False

        # Cleanup
        os.remove(db_path)

        return True

    except Exception as e:
        print(f"✗ Failed to reject confirmation: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_expired_confirmation():
    """Test that expired confirmations are filtered out."""
    print("\n=== Test 4: Expired Confirmation Handling ===")

    try:
        # Create temporary database
        db_path = "/tmp/test_expired_confirmation.db"
        if os.path.exists(db_path):
            os.remove(db_path)

        memory = MemoryStore(f"sqlite:///{db_path}")
        action_registry = ActionProviderRegistry(memory)
        action_router = ActionRouter(action_registry, memory)
        confirmation_manager = ConfirmationManager(memory, action_router)

        # Create confirmation that's already expired
        action_id = memory.create_action(
            user_id=1,
            session_id="test_session",
            action_type="create_calendar_event",
            category="calendar",
            intent_summary="Test expired",
            status="pending",
        )

        # Create confirmation with expiry in the past
        expires_at = datetime.utcnow() - timedelta(hours=1)
        confirmation_id = memory.create_confirmation(
            action_id=action_id,
            confirmation_message="This should be expired",
            expires_at=expires_at
        )

        print(f"✓ Created confirmation with past expiry: {expires_at}")

        # Get pending confirmations (should auto-expire)
        pending = confirmation_manager.get_pending_confirmations(user_id=1)

        if len(pending) == 0:
            print(f"✓ Expired confirmation filtered out")
        else:
            print(f"✗ Expected 0 pending confirmations, found {len(pending)}")
            return False

        # Verify confirmation status updated to expired
        conf = memory.get_confirmation_by_id(confirmation_id)
        if conf["status"] == "expired":
            print(f"✓ Confirmation marked as expired")
        else:
            print(f"✗ Confirmation status is {conf['status']}, expected 'expired'")
            return False

        # Cleanup
        os.remove(db_path)

        return True

    except Exception as e:
        print(f"✗ Failed to handle expired confirmation: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_unauthorized_access():
    """Test that users can't approve other users' confirmations."""
    print("\n=== Test 5: Unauthorized Access Prevention ===")

    try:
        # Create temporary database
        db_path = "/tmp/test_unauthorized.db"
        if os.path.exists(db_path):
            os.remove(db_path)

        memory = MemoryStore(f"sqlite:///{db_path}")
        action_registry = ActionProviderRegistry(memory)
        action_router = ActionRouter(action_registry, memory)
        confirmation_manager = ConfirmationManager(memory, action_router)

        # User 1 creates a confirmation
        confirmation = confirmation_manager.create_confirmation(
            user_id=1,
            session_id="test_session",
            action_type="create_calendar_event",
            action_params={"subject": "User 1's Event"},
            confirmation_message="Create event for user 1?",
        )

        # User 2 tries to approve it
        result = confirmation_manager.approve_confirmation(
            confirmation_id=confirmation["confirmation_id"],
            user_id=2  # Different user!
        )

        if result["status"] == "error" and "Unauthorized" in result["message"]:
            print(f"✓ Unauthorized access prevented")
            print(f"  - Error message: {result['message']}")
        else:
            print(f"✗ Expected authorization error, got: {result}")
            return False

        # Cleanup
        os.remove(db_path)

        return True

    except Exception as e:
        print(f"✗ Unauthorized access test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all Phase 5 tests."""
    print("=" * 60)
    print("Phase 5: Confirmation Workflow Tests")
    print("=" * 60)

    tests = [
        test_confirmation_manager_initialization,
        test_create_confirmation,
        test_reject_confirmation,
        test_expired_confirmation,
        test_unauthorized_access,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n✗ Test {test.__name__} crashed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

"""
Tests for Phase 4: Action Router with Calendar Read Handler

Tests:
1. Intent classification recognizes calendar queries
2. ActionRouter properly routes calendar requests
3. End-to-end calendar query flow
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.router import classify_intent
from core.action_router import ActionRouter
from actions.action_registry import ActionProviderRegistry
from core.memory import MemoryStore


def test_intent_classification():
    """Test that calendar queries are properly classified."""
    print("\n=== Test 1: Intent Classification ===")

    test_cases = [
        ("What's on my calendar tomorrow?", "read_calendar"),
        ("Am I free on Tuesday?", "read_calendar"),
        ("Show me my schedule", "read_calendar"),
        ("Book me a haircut", "book_appointment"),
        ("Send an email", "manage_email"),
        ("Hello, how are you?", "general"),
    ]

    for text, expected_intent in test_cases:
        intent = classify_intent(text, None)
        status = "✓" if intent == expected_intent else "✗"
        print(f"{status} '{text}' → {intent} (expected: {expected_intent})")

        if intent != expected_intent:
            print(f"  FAILED: Got {intent}, expected {expected_intent}")
            return False

    print("✓ All intent classification tests passed")
    return True


def test_action_router_initialization():
    """Test that ActionRouter can be initialized."""
    print("\n=== Test 2: ActionRouter Initialization ===")

    try:
        # Create temporary database
        db_path = "/tmp/test_action_router.db"
        if os.path.exists(db_path):
            os.remove(db_path)

        memory = MemoryStore(f"sqlite:///{db_path}")
        action_registry = ActionProviderRegistry(memory)
        action_router = ActionRouter(action_registry, memory)

        print("✓ ActionRouter initialized successfully")
        print(f"  - Registry: {action_registry}")
        print(f"  - Router: {action_router}")

        # Cleanup
        os.remove(db_path)

        return True

    except Exception as e:
        print(f"✗ Failed to initialize ActionRouter: {e}")
        return False


def test_calendar_query_no_provider():
    """Test calendar query when no M365 provider is configured."""
    print("\n=== Test 3: Calendar Query (No Provider) ===")

    try:
        # Create temporary database
        db_path = "/tmp/test_calendar_no_provider.db"
        if os.path.exists(db_path):
            os.remove(db_path)

        memory = MemoryStore(f"sqlite:///{db_path}")
        action_registry = ActionProviderRegistry(memory)
        action_router = ActionRouter(action_registry, memory)

        # Build context
        context = {
            "text": "What's on my calendar tomorrow?",
            "session_id": "test_session",
            "user_id": 1,
            "intent": "read_calendar",
        }

        # Route action
        result = action_router.route_action_request(context)

        print(f"✓ ActionRouter returned result")
        print(f"  - Provider: {result.get('provider')}")
        print(f"  - Task type: {result.get('task_type')}")
        print(f"  - Response: {result.get('text')[:100]}...")

        # Should return error about no provider
        if "don't have access" in result.get("text", "").lower():
            print("✓ Correctly returned 'no provider' error")
        else:
            print("✗ Expected 'no provider' error")
            return False

        # Cleanup
        os.remove(db_path)

        return True

    except Exception as e:
        print(f"✗ Calendar query failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_date_parsing():
    """Test natural language date parsing."""
    print("\n=== Test 4: Date Parsing ===")

    try:
        db_path = "/tmp/test_date_parsing.db"
        if os.path.exists(db_path):
            os.remove(db_path)

        memory = MemoryStore(f"sqlite:///{db_path}")
        action_registry = ActionProviderRegistry(memory)
        action_router = ActionRouter(action_registry, memory)

        test_cases = [
            "What's on my calendar tomorrow?",
            "Am I free on Tuesday?",
            "Show me my schedule for next week",
            "What's happening today?",
        ]

        for text in test_cases:
            date_range = action_router._parse_date_range(text)
            if date_range:
                start, end = date_range
                print(f"✓ '{text}'")
                print(f"  → {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")
            else:
                print(f"✗ Failed to parse: '{text}'")
                return False

        # Cleanup
        os.remove(db_path)

        print("✓ All date parsing tests passed")
        return True

    except Exception as e:
        print(f"✗ Date parsing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all Phase 4 tests."""
    print("=" * 60)
    print("Phase 4: Action Router Tests")
    print("=" * 60)

    tests = [
        test_intent_classification,
        test_action_router_initialization,
        test_date_parsing,
        test_calendar_query_no_provider,
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

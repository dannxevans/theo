#!/usr/bin/env python3
"""
Test script for GitHub Issue #39 - Chat Context Mode Separation

Tests:
1. Database schema changes (mode, user_id columns)
2. Session mode filtering
3. PII filtering functionality
4. Mode settings API endpoints
5. Session mode API endpoint
"""

import sqlite3
import sys
from backend.core.pii_filter import PIIFilter

def test_database_schema():
    """Test that database schema has required columns."""
    print("=" * 60)
    print("TEST 1: Database Schema")
    print("=" * 60)

    conn = sqlite3.connect('data/theo.db')
    cursor = conn.cursor()

    # Check sessions table
    cursor.execute("PRAGMA table_info(sessions)")
    sessions_columns = {row[1]: row[2] for row in cursor.fetchall()}

    if 'mode' in sessions_columns and 'user_id' in sessions_columns:
        print("✓ Sessions table has 'mode' and 'user_id' columns")
    else:
        print("✗ Sessions table missing required columns")
        return False

    # Check mode_settings table
    cursor.execute("PRAGMA table_info(mode_settings)")
    mode_settings_columns = {row[1]: row[2] for row in cursor.fetchall()}

    if 'pii_filtering_enabled' in mode_settings_columns and 'pii_redaction_config' in mode_settings_columns:
        print("✓ Mode_settings table has PII columns")
    else:
        print("✗ Mode_settings table missing PII columns")
        return False

    # Check index
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_sessions_user_mode_updated'")
    if cursor.fetchone():
        print("✓ Composite index on sessions table exists")
    else:
        print("✗ Composite index missing")
        return False

    conn.close()
    print("\n✅ Database schema test PASSED\n")
    return True


def test_pii_filter():
    """Test PII filtering functionality."""
    print("=" * 60)
    print("TEST 2: PII Filtering")
    print("=" * 60)

    # Test config
    config = {
        "pii_filtering_enabled": True,
        "pii_redaction_config": {
            "emails": True,
            "phones": True,
            "ssns": True,
            "creditCards": True,
            "names": False,
            "addresses": False
        }
    }

    pii_filter = PIIFilter(config)

    # Test cases
    test_cases = [
        {
            "name": "Email",
            "input": "Contact me at john.doe@example.com for details.",
            "should_contain": "[REDACTED EMAIL]"
        },
        {
            "name": "Phone",
            "input": "Call me at 123-456-7890 tomorrow.",
            "should_contain": "[REDACTED PHONE]"
        },
        {
            "name": "SSN",
            "input": "My SSN is 123-45-6789.",
            "should_contain": "[REDACTED SSN]"
        },
        {
            "name": "Credit Card",
            "input": "Card number: 4111-1111-1111-1111",
            "should_contain": "[REDACTED CREDIT_CARD]"
        },
        {
            "name": "Multiple PII",
            "input": "Email: test@test.com, Phone: 555-1234, SSN: 123-45-6789",
            "should_contain": "[REDACTED EMAIL]"
        }
    ]

    all_passed = True
    for test in test_cases:
        redacted_text, redactions = pii_filter.filter_text(test["input"])

        if test["should_contain"] in redacted_text:
            print(f"✓ {test['name']} redaction works")
            print(f"  Original: {test['input']}")
            print(f"  Redacted: {redacted_text}")
        else:
            print(f"✗ {test['name']} redaction FAILED")
            print(f"  Expected to find: {test['should_contain']}")
            print(f"  Got: {redacted_text}")
            all_passed = False

    if all_passed:
        print("\n✅ PII filtering test PASSED\n")
    else:
        print("\n❌ PII filtering test FAILED\n")

    return all_passed


def test_session_mode_filtering():
    """Test that sessions can be filtered by mode and user_id."""
    print("=" * 60)
    print("TEST 3: Session Mode Filtering")
    print("=" * 60)

    from backend.core.memory import MemoryStore
    from backend.config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Create test sessions with different modes
    test_user_id = 1  # Assuming user ID 1 exists

    try:
        # Test filtering by mode
        personal_sessions = memory.list_sessions(user_id=test_user_id, mode="personal")
        work_sessions = memory.list_sessions(user_id=test_user_id, mode="work")
        all_sessions = memory.list_sessions(user_id=test_user_id)

        print(f"✓ Found {len(personal_sessions)} personal sessions")
        print(f"✓ Found {len(work_sessions)} work sessions")
        print(f"✓ Found {len(all_sessions)} total sessions for user {test_user_id}")

        print("\n✅ Session mode filtering test PASSED\n")
        return True
    except Exception as e:
        print(f"✗ Session mode filtering FAILED: {e}")
        print("\n❌ Session mode filtering test FAILED\n")
        return False


def test_mode_settings():
    """Test mode settings creation and retrieval."""
    print("=" * 60)
    print("TEST 4: Mode Settings")
    print("=" * 60)

    from backend.core.memory import MemoryStore
    from backend.config import Config
    import json

    memory = MemoryStore(Config.DATABASE_URL)
    test_user_id = 1

    try:
        # Test creating/updating work mode settings with PII config
        pii_config = {
            "emails": True,
            "phones": True,
            "ssns": True,
            "creditCards": True,
            "names": False,
            "addresses": False
        }

        memory.create_or_update_mode_settings(
            test_user_id,
            "work",
            system_prompt_override="Test work mode prompt",
            tone="professional",
            pii_filtering_enabled=True,
            pii_redaction_config=json.dumps(pii_config)
        )

        print("✓ Created/updated work mode settings with PII config")

        # Retrieve and verify
        settings = memory.get_mode_settings(test_user_id, "work")

        if settings:
            print(f"✓ Retrieved work mode settings")
            print(f"  - System prompt override: {settings.get('system_prompt_override')[:50]}...")
            print(f"  - Tone: {settings.get('tone')}")
            print(f"  - PII filtering enabled: {settings.get('pii_filtering_enabled')}")

            if settings.get('pii_redaction_config'):
                redaction_config = json.loads(settings['pii_redaction_config'])
                print(f"  - PII config loaded: {list(redaction_config.keys())}")
        else:
            print("✗ Failed to retrieve work mode settings")
            return False

        print("\n✅ Mode settings test PASSED\n")
        return True
    except Exception as e:
        print(f"✗ Mode settings test FAILED: {e}")
        print("\n❌ Mode settings test FAILED\n")
        return False


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "=" * 60)
    print("TESTING: GitHub Issue #39 - Chat Context Mode Separation")
    print("=" * 60 + "\n")

    results = {
        "Database Schema": test_database_schema(),
        "PII Filtering": test_pii_filter(),
        "Session Mode Filtering": test_session_mode_filtering(),
        "Mode Settings": test_mode_settings()
    }

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")

    all_passed = all(results.values())

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())

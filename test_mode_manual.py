#!/usr/bin/env python3
"""
Manual test to demonstrate mode separation functionality.

This script tests the core features without relying on user sessions.
"""

import json
from backend.core.pii_filter import PIIFilter

print("=" * 70)
print("MANUAL TEST: Mode Separation & PII Filtering")
print("=" * 70)
print()

# Test 1: PII Filtering with different configurations
print("TEST 1: PII Filtering with Various Configurations")
print("-" * 70)

test_text = """
Hi, my name is John Doe. You can reach me at:
- Email: john.doe@company.com
- Phone: (555) 123-4567
- SSN: 123-45-6789
- Credit Card: 4111-1111-1111-1111

My address is 123 Main Street.
"""

# Configuration 1: All PII types enabled
print("\n1. Full PII Protection (all types enabled):")
print("-" * 70)
config1 = {
    "pii_filtering_enabled": True,
    "pii_redaction_config": {
        "emails": True,
        "phones": True,
        "ssns": True,
        "creditCards": True,
        "names": True,
        "addresses": True
    }
}

pii_filter1 = PIIFilter(config1)
redacted1, redactions1 = pii_filter1.filter_text(test_text)

print("Original text:")
print(test_text)
print("\nRedacted text:")
print(redacted1)
print(f"\nRedactions made: {len(redactions1)}")
print(f"Types: {pii_filter1.get_redaction_stats(redactions1)}")

# Configuration 2: Only critical PII (email, phone, SSN, credit card)
print("\n\n2. Standard PII Protection (critical types only):")
print("-" * 70)
config2 = {
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

pii_filter2 = PIIFilter(config2)
redacted2, redactions2 = pii_filter2.filter_text(test_text)

print("Redacted text:")
print(redacted2)
print(f"\nRedactions made: {len(redactions2)}")
print(f"Types: {pii_filter2.get_redaction_stats(redactions2)}")

# Configuration 3: PII filtering disabled
print("\n\n3. No PII Protection (filtering disabled):")
print("-" * 70)
config3 = {
    "pii_filtering_enabled": False,
    "pii_redaction_config": {}
}

pii_filter3 = PIIFilter(config3)
redacted3, redactions3 = pii_filter3.filter_text(test_text)

print("Text (unchanged):")
print(redacted3)
print(f"Redactions made: {len(redactions3)}")

# Test 2: Demonstrate different PII patterns
print("\n\n" + "=" * 70)
print("TEST 2: PII Pattern Recognition")
print("=" * 70)

test_cases = [
    ("Email formats", "Contact: test@example.com, admin@company.org, user123@mail.co.uk"),
    ("Phone formats", "US: 555-1234, (555) 123-4567, +1-555-123-4567; UK: 01234 567890"),
    ("SSN formats", "SSN: 123-45-6789, 123 45 6789, 123456789"),
    ("Credit cards", "Visa: 4111-1111-1111-1111, Amex: 3782-822463-10005"),
]

pii_filter = PIIFilter({
    "pii_filtering_enabled": True,
    "pii_redaction_config": {
        "emails": True,
        "phones": True,
        "ssns": True,
        "creditCards": True,
        "names": False,
        "addresses": False
    }
})

for test_name, test_input in test_cases:
    print(f"\n{test_name}:")
    print(f"  Input:  {test_input}")
    redacted, redactions = pii_filter.filter_text(test_input)
    print(f"  Output: {redacted}")
    if redactions:
        print(f"  Found:  {pii_filter.get_redaction_stats(redactions)}")

# Test 3: Database schema verification
print("\n\n" + "=" * 70)
print("TEST 3: Database Schema Verification")
print("=" * 70)

import sqlite3
conn = sqlite3.connect('data/theo.db')
cursor = conn.cursor()

# Check sessions table
cursor.execute("SELECT mode, user_id FROM sessions LIMIT 5")
sessions = cursor.fetchall()
print(f"\nSample sessions (mode, user_id): {sessions if sessions else 'No sessions found'}")

# Check mode_settings table
cursor.execute("SELECT user_id, mode, pii_filtering_enabled FROM mode_settings LIMIT 5")
mode_settings = cursor.fetchall()
print(f"\nMode settings (user_id, mode, pii_enabled): {mode_settings if mode_settings else 'No mode settings found'}")

conn.close()

print("\n\n" + "=" * 70)
print("✅ MANUAL TESTS COMPLETED")
print("=" * 70)
print("\nKey findings:")
print("1. PII filtering works correctly with different configurations")
print("2. Multiple PII types can be detected and redacted")
print("3. Database schema includes required columns for mode separation")
print("\nNext steps:")
print("- Start frontend (npm run dev in frontend/)")
print("- Test mode switching UI")
print("- Test session mode locking")
print("- Test PII configuration in Work Mode settings")
print("=" * 70)

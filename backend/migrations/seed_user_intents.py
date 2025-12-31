#!/usr/bin/env python3
"""
Seed default intents for a specific user.

Usage:
    python3 /app/migrations/seed_user_intents.py <database_path> <user_id>

Example:
    python3 /app/migrations/seed_user_intents.py /data/theo.db 1
"""

import sys
import os

# Add /app to Python path so we can import from core
app_dir = '/app'
if os.path.exists(app_dir):
    sys.path.insert(0, app_dir)
else:
    # Fallback for local development
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory import MemoryStore


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 seed_user_intents.py <database_path> <user_id>")
        print("Example: python3 seed_user_intents.py /data/theo.db 1")
        sys.exit(1)

    db_path = sys.argv[1]
    user_id = sys.argv[2]

    # Construct database URL
    if not db_path.startswith('sqlite:///'):
        db_url = f"sqlite:///{db_path}"
    else:
        db_url = db_path

    print(f"🔍 Connecting to database: {db_url}")
    memory = MemoryStore(db_url)

    print(f"📋 Checking existing intents for user_id={user_id}...")
    existing_intents = memory.list_intents(user_id)

    if existing_intents:
        print(f"✅ Found {len(existing_intents)} existing intents:")
        for intent in existing_intents:
            action_marker = " [ACTION]" if intent.get('is_action') else ""
            print(f"   - {intent['id']}{action_marker}")
        print()
        response = input("❓ Do you want to seed anyway? This will skip existing intents. (y/N): ")
        if response.lower() != 'y':
            print("❌ Aborted")
            sys.exit(0)

    print(f"🌱 Seeding default intents for user_id={user_id}...")
    try:
        memory.seed_default_intents(user_id)
        print(f"✅ Successfully seeded default intents!")

        # List all intents after seeding
        all_intents = memory.list_intents(user_id)
        print(f"\n📋 Total intents for user_id={user_id}: {len(all_intents)}")

        llm_intents = [i for i in all_intents if not i.get('is_action')]
        action_intents = [i for i in all_intents if i.get('is_action')]

        if llm_intents:
            print(f"\n🤖 LLM Routing Intents ({len(llm_intents)}):")
            for intent in llm_intents:
                print(f"   - {intent['id']}: {intent['name']}")

        if action_intents:
            print(f"\n⚡ Action Intents ({len(action_intents)}):")
            for intent in action_intents:
                print(f"   - {intent['id']}: {intent['name']}")

    except Exception as e:
        print(f"❌ Error seeding intents: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

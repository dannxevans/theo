#!/usr/bin/env python3
"""Test WHOOP V2 API recovery data fetch."""

import sys
from core.memory import MemoryStore
from core.proactive.whoop_stress_service import WHOOPStressService

def main():
    import os
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'theo.db')
    memory = MemoryStore(f'sqlite:///{db_path}')
    service = WHOOPStressService(memory)

    print("[TEST] Starting WHOOP stress check...")
    result = service.check_and_notify(1)
    print(f"[TEST] Result: {result}")

    if result:
        print("[TEST] ✓ Notification sent successfully!")
    else:
        print("[TEST] ✗ No notification sent")

if __name__ == "__main__":
    main()

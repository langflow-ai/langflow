#!/usr/bin/env python3
"""Test memory functionality on release-1.6.0 branch"""

import asyncio
from uuid import uuid4
from langflow.memory import astore_message, aget_messages
from langflow.schema.message import Message

async def test_memory_with_limit():
    session_id = f"test_session_{uuid4().hex[:8]}"
    
    # Store 6 messages
    for i in range(1, 7):
        message = Message(
            text=f"Message {i}: Test message number {i}",
            sender="User",
            sender_name="TestUser",
            session_id=session_id
        )
        await astore_message(message)
        print(f"Stored: {message.text}")
    
    # Test retrieving with limit=3
    print("\n=== Testing with limit=3 ===")
    messages = await aget_messages(session_id=session_id, limit=3, order="Ascending")
    print(f"Retrieved {len(messages)} messages:")
    for msg in messages:
        print(f"  - {msg.text}")
    
    # Test retrieving all
    print("\n=== Testing with no limit ===")
    all_messages = await aget_messages(session_id=session_id, order="Ascending")
    print(f"Retrieved {len(all_messages)} messages:")
    for msg in all_messages:
        print(f"  - {msg.text}")

if __name__ == "__main__":
    asyncio.run(test_memory_with_limit())
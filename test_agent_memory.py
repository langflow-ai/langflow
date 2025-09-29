#!/usr/bin/env python3
"""Test script to verify agent n_messages parameter functionality using API calls."""

import requests
import json
import time

def test_agent_memory_api():
    """Test agent memory with n_messages=3 using API calls."""
    
    # Flow configuration
    flow_url = "http://localhost:7860/api/v1/run/1957a791-5284-4f72-9ba2-aecb564d67b6"
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': 'sk-jHb9j2Gs7jlx5zc6GB8si1ZpMq6NSMLpsJ-Jtj5hDDo'
    }
    
    # Generate unique session ID for this test
    import uuid
    session_id = f"memory_test_{uuid.uuid4()}"
    print(f"Test session ID: {session_id}")
    
    # Test conversation sequence
    test_messages = [
        "Message 1: Hello, this is the first test message.",
        "Message 2: This is the second test message.", 
        "Message 3: This is the third test message.",
        "Message 4: This is the fourth test message.",
        "Message 5: This is the fifth test message.",
        "Final question: I want you to recall our entire conversation history. Please list ALL the previous messages you can remember from this session, including my messages that started with 'Message 1:', 'Message 2:', etc. Be thorough and include everything you can recall."
    ]
    
    print("Starting conversation test...")
    print("NOTE: Make sure your agent has n_messages=3 configured")
    print("=" * 60)
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n[Message {i}] User: {message}")
        
        # Prepare API request
        data = {
            "input_value": message,
            "session_id": session_id,
            "stream": False
        }
        
        try:
            # Make API call
            response = requests.post(f"{flow_url}?stream=false", 
                                   headers=headers, 
                                   json=data, 
                                   timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                print(f"[DEBUG] Response structure: {json.dumps(result, indent=2)[:500]}...")
                
                # Try to extract the agent response from various possible paths
                agent_response = None
                try:
                    if 'outputs' in result and len(result['outputs']) > 0:
                        # Try different possible paths
                        outputs = result['outputs'][0]
                        if 'outputs' in outputs and len(outputs['outputs']) > 0:
                            results = outputs['outputs'][0].get('results', {})
                            # Try different result keys
                            for key in ['response', 'text', 'message', 'output']:
                                if key in results:
                                    data = results[key]
                                    if isinstance(data, dict):
                                        agent_response = data.get('text') or data.get('content') or str(data)
                                    else:
                                        agent_response = str(data)
                                    break
                    
                    if not agent_response:
                        agent_response = str(result)
                        
                except Exception as e:
                    agent_response = f"Error parsing response: {e}"
                
                print(f"[Response {i}] Agent: {agent_response}")
                
                # If this is the final question, analyze the response
                if "recall our entire conversation history" in message:
                    print("\n" + "=" * 60)
                    print("ANALYSIS OF AGENT MEMORY:")
                    print("Expected: Agent should only remember the last 3 messages")
                    print("(messages 4, 5, and the final question)")
                    print(f"Actual response: {agent_response}")
                    print("=" * 60)
                    
                    # Check if agent mentions all 6 messages or just the last 3
                    message_count = 0
                    for j in range(1, 7):
                        if f"Message {j}" in agent_response or f"message {j}" in agent_response.lower():
                            message_count += 1
                    
                    print(f"\nAgent mentioned {message_count} out of 6 messages")
                    if message_count <= 3:
                        print("✅ PASS: Agent correctly limited memory to last 3 messages")
                    else:
                        print("❌ FAIL: Agent remembered more than 3 messages")
            else:
                print(f"[Response {i}] Error: HTTP {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"[Response {i}] Error: {e}")
        
        # Small delay between messages
        time.sleep(1)

if __name__ == "__main__":
    test_agent_memory_api()
#!/bin/bash

# Test agent memory with n_messages=3 using batch curl requests
SESSION_ID="memory_test_batch_$(date +%s)"
API_KEY="sk-jHb9j2Gs7jlx5zc6GB8si1ZpMq6NSMLpsJ-Jtj5hDDo"
FLOW_URL="http://localhost:7860/api/v1/run/1957a791-5284-4f72-9ba2-aecb564d67b6?stream=false"

echo "Testing agent memory with session: $SESSION_ID"
echo "============================================================"

# Send all 6 messages
messages=(
    "Message 1: Hello, this is the first test message."
    "Message 2: This is the second test message."
    "Message 3: This is the third test message."
    "Message 4: This is the fourth test message."
    "Message 5: This is the fifth test message."
    "Please recall our entire conversation history. List ALL the previous messages you can remember from this session, including my messages that started with Message 1, Message 2, etc. Be thorough and include everything you can recall."
)

for i in "${!messages[@]}"; do
    msg_num=$((i + 1))
    echo ""
    echo "[Message $msg_num] Sending: ${messages[$i]}"
    
    response=$(curl -s --request POST \
        --url "$FLOW_URL" \
        --header "x-api-key: $API_KEY" \
        --header 'Content-Type: application/json' \
        --data "{\"input_value\": \"${messages[$i]}\", \"session_id\": \"$SESSION_ID\"}")
    
    # Extract just the text response
    agent_response=$(echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data['outputs'][0]['outputs'][0]['results']['message']['text'])
except:
    print('Error parsing response')
")
    
    echo "[Response $msg_num] Agent: $agent_response"
    
    # If this is the final message, analyze the response
    if [ $msg_num -eq 6 ]; then
        echo ""
        echo "============================================================"
        echo "ANALYSIS OF AGENT MEMORY:"
        echo "Expected: Agent should only remember the last 3 messages"
        echo "(messages 4, 5, and the final question)"
        echo "Actual response: $agent_response"
        echo "============================================================"
        
        # Count how many messages the agent mentioned
        count=0
        for j in {1..5}; do
            if echo "$agent_response" | grep -qi "Message $j"; then
                count=$((count + 1))
            fi
        done
        
        echo ""
        echo "Agent mentioned $count out of 5 previous messages"
        if [ $count -le 3 ]; then
            echo "✅ PASS: Agent correctly limited memory to last 3 messages"
        else
            echo "❌ FAIL: Agent remembered more than 3 messages"
        fi
    fi
    
    sleep 1
done
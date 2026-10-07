curl -X POST \
  "$LANGFLOW_SERVER_URL/api/v2/workflows" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{
    "flow_id": "'"${FLOW_ID}"'",
    "input_value": "what is 2+2",
    "session_id": "session-123",
    "mode": "sync"
  }'

curl -X POST \
  "$LANGFLOW_SERVER_URL/api/v1/run/$FLOW_ID" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{
    "input_value": "Tell me about something interesting!",
    "session_id": "chat-123",
    "input_type": "chat",
    "output_type": "chat",
    "output_component": ""
  }'

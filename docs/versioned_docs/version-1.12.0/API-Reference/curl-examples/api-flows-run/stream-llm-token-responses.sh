curl -X POST \
  "$LANGFLOW_SERVER_URL/api/v1/run/$FLOW_ID?stream=true" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{
    "message": "Tell me something interesting!",
    "session_id": "chat-123"
  }'

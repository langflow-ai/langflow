curl -X POST \
  "$LANGFLOW_SERVER_URL/api/v1/run/$FLOW_ID?stream=true" \
  -H "Content-Type: application/json" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{
    "input_value": "Tell me a story",
    "input_type": "chat",
    "output_type": "chat",
    "output_component": "chat_output",
    "session_id": "chat-123",
    "tweaks": {
      "component_id": {
        "parameter_name": "value"
      }
    }
  }'

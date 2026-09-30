curl -X POST \
  "$LANGFLOW_SERVER_URL/api/v2/workflows" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{
    "flow_id": "flow_67ccd2be17f0819081ff3bb2cf6508e60bb6a6b452d3795b",
    "background": false,
    "inputs": {
      "ChatInput-abc.input_type": "chat",
      "ChatInput-abc.input_value": "what is 2+2",
      "ChatInput-abc.session_id": "session-123"
    }
  }'

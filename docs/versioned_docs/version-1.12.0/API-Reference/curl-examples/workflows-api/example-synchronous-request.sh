curl -X POST \
  "$LANGFLOW_SERVER_URL/api/v2/workflows" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{
    "flow_id": "67ccd2be-17f0-8190-81ff-3bb2cf6508e6",
    "input_value": "what is 2+2",
    "session_id": "session-123",
    "mode": "sync",
    "globals": {
      "FILENAME": "relatório—final.pdf",
      "OWNER_NAME": "José"
    }
  }'

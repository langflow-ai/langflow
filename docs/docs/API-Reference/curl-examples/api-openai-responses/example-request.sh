curl -X POST \
  "$LANGFLOW_SERVER_URL/api/v1/responses" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "$YOUR_FLOW_ID",
    "input": "Hello, how are you?",
    "stream": false
  }'

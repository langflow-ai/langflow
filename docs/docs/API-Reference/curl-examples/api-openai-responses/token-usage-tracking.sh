curl -X POST \
  "$LANGFLOW_SERVER_URL/api/v1/responses" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "FLOW_ID",
    "input": "Explain quantum computing in simple terms",
    "stream": false
  }'

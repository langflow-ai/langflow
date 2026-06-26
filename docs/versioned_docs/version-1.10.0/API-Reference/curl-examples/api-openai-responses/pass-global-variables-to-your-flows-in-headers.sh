curl -X POST \
  "$LANGFLOW_SERVER_URL/api/v1/responses" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-LANGFLOW-GLOBAL-VAR-OPENAI_API_KEY: sk-..." \
  -H "X-LANGFLOW-GLOBAL-VAR-USER_ID: user123" \
  -H "X-LANGFLOW-GLOBAL-VAR-ENVIRONMENT: production" \
  -d '{
    "model": "your-flow-id",
    "input": "Hello"
  }'

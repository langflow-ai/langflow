curl -X PUT \
  "$LANGFLOW_URL/api/v1/monitor/messages/3ab66cc6-c048-48f8-ab07-570f5af7b160" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{
  "text": "testing 1234"
}'

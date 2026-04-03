curl -X GET \
  "$LANGFLOW_URL/logs-stream" \
  -H "accept: text/event-stream" \
  -H "x-api-key: $LANGFLOW_API_KEY"

curl -X GET \
  "$LANGFLOW_URL/api/v1/monitor/builds?flow_id=$FLOW_ID" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY"

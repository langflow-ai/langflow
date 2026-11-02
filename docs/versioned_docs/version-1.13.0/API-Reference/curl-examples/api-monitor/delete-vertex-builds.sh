curl -X DELETE \
  "$LANGFLOW_URL/api/v1/monitor/builds?flow_id=$FLOW_ID" \
  -H "accept: */*" \
  -H "x-api-key: $LANGFLOW_API_KEY"

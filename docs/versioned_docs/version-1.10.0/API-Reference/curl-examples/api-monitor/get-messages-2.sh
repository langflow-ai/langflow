curl -X GET \
  "$LANGFLOW_URL/api/v1/monitor/messages?flow_id=$FLOW_ID&session_id=01ce083d-748b-4b8d-97b6-33adbb6a528a&sender=Machine&sender_name=AI&order_by=timestamp" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY"

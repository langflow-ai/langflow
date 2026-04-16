curl -X DELETE \
  "$LANGFLOW_URL/api/v1/monitor/messages/session/different_session_id_2" \
  -H "accept: */*" \
  -H "x-api-key: $LANGFLOW_API_KEY"

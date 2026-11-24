curl -X DELETE \
  "$LANGFLOW_URL/api/v2/files/$FILE_ID" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY"

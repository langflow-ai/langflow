curl -X DELETE \
  "$LANGFLOW_URL/api/v1/projects/$PROJECT_ID" \
  -H "accept: */*" \
  -H "x-api-key: $LANGFLOW_API_KEY"

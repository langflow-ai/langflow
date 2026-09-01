curl -X GET \
  "$LANGFLOW_URL/api/v1/projects/download/$PROJECT_ID" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  --output langflow-project.zip

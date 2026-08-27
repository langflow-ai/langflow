curl -X GET \
  "$LANGFLOW_URL/api/v2/files/c7b22c4c-d5e0-4ec9-af97-5d85b7657a34" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  --output downloaded_file.txt

curl -X POST \
  "$LANGFLOW_URL/api/v1/projects/" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{
  "name": "new_project_name",
  "description": "string",
  "components_list": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ],
  "flows_list": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ]
}'

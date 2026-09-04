curl -X PATCH \
  "$LANGFLOW_URL/api/v1/projects/b408ddb9-6266-4431-9be8-e04a62758331" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{
  "name": "string",
  "description": "string",
  "parent_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "components": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ],
  "flows": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ]
}'

curl -X POST \
  "$LANGFLOW_URL/api/v1/flows/" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{
  "name": "string2",
  "description": "string",
  "icon": "string",
  "icon_bg_color": "#FF0000",
  "gradient": "string",
  "data": {},
  "is_component": false,
  "updated_at": "2024-12-30T15:48:01.519Z",
  "webhook": false,
  "endpoint_name": "string",
  "tags": [
    "string"
  ]
}'

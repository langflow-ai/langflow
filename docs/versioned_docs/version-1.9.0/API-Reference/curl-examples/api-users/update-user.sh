curl -X PATCH \
  "$LANGFLOW_URL/api/v1/users/10c1c6a2-ab8a-4748-8700-0e4832fd5ce8" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{
    "is_active": true,
    "is_superuser": true
  }'

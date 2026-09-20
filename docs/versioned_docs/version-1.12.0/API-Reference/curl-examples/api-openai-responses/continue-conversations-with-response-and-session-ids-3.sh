BASE_URL="${LANGFLOW_SERVER_URL:-$LANGFLOW_URL}"

curl -X POST \
  "$BASE_URL/api/v1/responses" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "model": "$FLOW_ID",
  "input": "What's my name?",
  "previous_response_id": "session-alice-1756839048"
}
EOF

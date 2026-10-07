BASE_URL="${LANGFLOW_SERVER_URL:-$LANGFLOW_URL}"

curl -X POST \
  "$BASE_URL/api/v1/responses" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "model": "$FLOW_ID",
  "input": "What's my name?",
  "previous_response_id": "c45f4ac8-772b-4675-8551-c560b1afd590"
}
EOF

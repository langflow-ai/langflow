BASE_URL="${LANGFLOW_SERVER_URL:-$LANGFLOW_URL}"

curl -X POST \
  "$BASE_URL/api/v1/responses" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d @- <<EOF
{
    "model": "$FLOW_ID",
    "input": "Calculate 23 * 15 and show me the result",
    "stream": false,
    "include": ["tool_call.results"]
}
EOF

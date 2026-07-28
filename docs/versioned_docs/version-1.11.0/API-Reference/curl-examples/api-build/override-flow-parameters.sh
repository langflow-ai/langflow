curl -X POST \
  "$LANGFLOW_URL/api/v1/build/$FLOW_ID/flow" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{
    "data": {
      "nodes": [],
      "edges": []
    },
    "inputs": {
      "input_value": "Your custom input here",
      "session": "session_id"
    }
  }'

curl -X POST \
  "$LANGFLOW_URL/api/v1/build/$FLOW_ID/flow" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{"stop_component_id": "OpenAIModel-Uksag"}'

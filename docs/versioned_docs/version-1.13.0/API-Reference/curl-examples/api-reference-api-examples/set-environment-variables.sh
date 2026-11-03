# Set environment variables (allow callers/wrappers to override defaults)
export LANGFLOW_API_KEY="${LANGFLOW_API_KEY:-sk-local-placeholder}"
export LANGFLOW_SERVER_URL="${LANGFLOW_SERVER_URL:-http://localhost:7860}"
export FLOW_ID="${FLOW_ID:-359cd752-07ea-46f2-9d3b-a4407ef618da}"
export PROJECT_ID="${PROJECT_ID:-1415de42-8f01-4f36-bf34-539f23e47466}"

# Use environment variables in API requests
curl --request POST \
  --url "$LANGFLOW_SERVER_URL/api/v1/run/$FLOW_ID?stream=false" \
  --header "Content-Type: application/json" \
  --header "x-api-key: $LANGFLOW_API_KEY" \
  --data '{
  "input_value": "hello world!",
  "output_type": "chat",
  "input_type": "chat",
  "tweaks": {
    "ChatOutput-6zcZt": {
      "should_store_message": true
    }
  }
}'

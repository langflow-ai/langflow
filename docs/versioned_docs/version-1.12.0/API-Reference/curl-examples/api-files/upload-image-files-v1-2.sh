curl -X POST \
    "$LANGFLOW_URL/api/v1/run/a430cc57-06bb-4c11-be39-d3d4de68d2c4?stream=false" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $LANGFLOW_API_KEY" \
    -d '{
    "output_type": "chat",
    "input_type": "chat",
    "tweaks": {
      "ChatInput-b67sL": {
        "files": "a430cc57-06bb-4c11-be39-d3d4de68d2c4/2024-11-27_14-47-50_image-file.png",
        "input_value": "describe this image"
      }
    }
  }'

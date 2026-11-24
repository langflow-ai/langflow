curl --request POST \
  --url "$LANGFLOW_URL/api/v1/run/$FLOW_ID" \
  --header "Content-Type: application/json" \
  --header "x-api-key: $LANGFLOW_API_KEY" \
  --data '{
  "input_value": "what do you see?",
  "output_type": "chat",
  "input_type": "text",
  "tweaks": {
    "Read-File-1olS3": {
      "path": [
        "07e5b864-e367-4f52-b647-a48035ae7e5e/3a290013-fe1e-4d3d-a454-cacae81288f3.pdf"
      ]
    }
  }
}'

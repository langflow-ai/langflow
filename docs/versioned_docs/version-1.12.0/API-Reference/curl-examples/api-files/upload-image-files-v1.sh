SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_IMAGE_FILE="$SCRIPT_DIR/../../fixtures/sample-upload.png"
IMAGE_FILE="${SAMPLE_IMAGE_FILE:-$DEFAULT_IMAGE_FILE}"

curl -X POST "$LANGFLOW_URL/api/v1/files/upload/$FLOW_ID" \
  -H "Content-Type: multipart/form-data" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -F "file=@${IMAGE_FILE}"

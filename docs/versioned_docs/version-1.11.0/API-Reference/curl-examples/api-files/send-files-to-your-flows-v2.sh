SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_UPLOAD_FILE="$SCRIPT_DIR/../../fixtures/sample-upload.txt"
UPLOAD_FILE="${SAMPLE_UPLOAD_FILE:-$DEFAULT_UPLOAD_FILE}"

curl -X POST \
  "$LANGFLOW_URL/api/v2/files" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -F "file=@${UPLOAD_FILE}"

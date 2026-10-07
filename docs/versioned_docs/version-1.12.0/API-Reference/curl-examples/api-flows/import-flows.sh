SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_FLOW_IMPORT_FILE="$SCRIPT_DIR/../../fixtures/flow-import.json"
FLOW_IMPORT_FILE="${FLOW_IMPORT_FILE:-$DEFAULT_FLOW_IMPORT_FILE}"

curl -X POST \
  "$LANGFLOW_URL/api/v1/flows/upload/?folder_id=$FOLDER_ID" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -F "file=@${FLOW_IMPORT_FILE};type=application/json"

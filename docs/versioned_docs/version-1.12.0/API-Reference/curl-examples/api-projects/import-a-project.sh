SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PROJECT_IMPORT_FILE="$SCRIPT_DIR/../../fixtures/project-import.json"
PROJECT_IMPORT_FILE="${PROJECT_IMPORT_JSON:-${PROJECT_IMPORT_FILE:-$DEFAULT_PROJECT_IMPORT_FILE}}"

curl -X POST \
  "$LANGFLOW_URL/api/v1/projects/upload/" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -F "file=@${PROJECT_IMPORT_FILE};type=application/json"

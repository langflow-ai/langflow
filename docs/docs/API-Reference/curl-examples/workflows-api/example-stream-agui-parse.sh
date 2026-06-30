#!/usr/bin/env bash
# Parse AG-UI SSE frames with jq and chain two workflow runs in one session.
set -euo pipefail

BASE="${LANGFLOW_URL:-${LANGFLOW_SERVER_URL:-}}"
FLOW_ID="${FLOW_ID:-67ccd2be-17f0-8190-81ff-3bb2cf6508e6}"
API_KEY="${LANGFLOW_API_KEY:-}"
SESSION_ID="${AGUI_SESSION_ID:-thread-123}"
MULTIPLIER="${AGUI_MULTIPLIER:-3}"
PROMPT1="${AGUI_PROMPT1:-What is 847 divided by 7?}"

TEXT_FILE="$(mktemp)"
TOOLS_FILE="$(mktemp)"
trap 'rm -f "$TEXT_FILE" "$TOOLS_FILE"' EXIT

extract_number() {
  local text last=""
  text="$(cat "$TEXT_FILE")"
  while IFS= read -r line; do
    if [[ "$line" =~ (-?[0-9]+(\.[0-9]+)?) ]]; then
      echo "${BASH_REMATCH[1]}"
      return 0
    fi
  done < <(tac "$TOOLS_FILE" 2>/dev/null || tail -r "$TOOLS_FILE")
  while read -r num; do
    last="$num"
  done < <(grep -oE -- '-?[0-9]+(\.[0-9]+)?' <<< "$text" || true)
  if [[ -n "$last" ]]; then
    echo "$last"
  fi
}

ask() {
  local prompt="$1"
  : > "$TEXT_FILE"
  : > "$TOOLS_FILE"
  curl -N -s -X POST "${BASE}/api/v2/workflows" \
    -H "Content-Type: application/json" \
    -H "x-api-key: ${API_KEY}" \
    -d "$(jq -n \
      --arg flow_id "$FLOW_ID" \
      --arg input_value "$prompt" \
      --arg session_id "$SESSION_ID" \
      '{flow_id: $flow_id, input_value: $input_value, mode: "stream", stream_protocol: "agui", session_id: $session_id}')" \
  | while IFS= read -r line; do
      [[ "$line" == data:* ]] || continue
      json="${line#data: }"
      case "$(jq -r '.type' <<<"$json")" in
        TEXT_MESSAGE_CONTENT)
          jq -r '.delta // ""' <<<"$json" >> "$TEXT_FILE"
          ;;
        TOOL_CALL_RESULT)
          jq -r '.content // .result // ""' <<<"$json" >> "$TOOLS_FILE"
          ;;
        RUN_ERROR)
          jq -r '.message // "Run failed"' <<<"$json" >&2
          exit 1
          ;;
        RUN_FINISHED)
          break
          ;;
      esac
    done
}

echo "User: ${PROMPT1}"
ask "$PROMPT1"
QUOTIENT="$(extract_number)"
if [[ -z "${QUOTIENT:-}" ]]; then
  echo "Could not extract a number from run 1." >&2
  exit 1
fi
echo "Assistant: $(tr -d '\n' < "$TEXT_FILE")"
echo "Extracted: ${QUOTIENT}"

PROMPT2="${AGUI_PROMPT2:-Now multiply ${QUOTIENT} by ${MULTIPLIER}.}"
echo
echo "User: ${PROMPT2}"
ask "$PROMPT2"
PRODUCT="$(extract_number)"
if [[ -z "${PRODUCT:-}" ]]; then
  echo "Could not extract a number from run 2." >&2
  exit 1
fi
echo "Assistant: $(tr -d '\n' < "$TEXT_FILE")"

echo
echo "=== Calculation chain ==="
echo "847 ÷ 7 = ${QUOTIENT}"
echo "${QUOTIENT} × ${MULTIPLIER} = ${PRODUCT}"

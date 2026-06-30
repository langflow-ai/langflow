#!/usr/bin/env bash
set -euo pipefail

JOB_ID="$(
  curl -s -X POST \
    "$LANGFLOW_SERVER_URL/api/v2/workflows" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $LANGFLOW_API_KEY" \
    -d '{
      "flow_id": "'"${FLOW_ID}"'",
      "input_value": "Process this in the background",
      "session_id": "session-456",
      "mode": "background"
    }' | python3 -c 'import json,sys; print(json.load(sys.stdin)["job_id"])'
)"

echo "Queued job $JOB_ID"

while true; do
  BODY="$(curl -s \
    "$LANGFLOW_SERVER_URL/api/v2/workflows?job_id=$JOB_ID" \
    -H "x-api-key: $LANGFLOW_API_KEY")"
  STATUS="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))' <<<"$BODY")"
  OBJECT="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("object",""))' <<<"$BODY")"

  if [[ "$OBJECT" == "response" && "$STATUS" == "completed" ]]; then
    python3 -c 'import json,sys; print(json.load(sys.stdin)["output"]["text"])' <<<"$BODY"
    break
  fi

  if [[ "$STATUS" == "failed" || "$STATUS" == "cancelled" || "$STATUS" == "timed_out" ]]; then
    echo "Job ended with status $STATUS" >&2
    exit 1
  fi

  sleep 1
done

#!/usr/bin/env bash
# Supply a connection for one lfx serve request.
#
# global_vars is per-request: it is applied to a deep copy of the graph and bound
# to this request only, so it never becomes an ambient default for the next caller
# on the same warm worker. Start the server with --no-env-fallback to make that the
# only accepted channel.
set -euo pipefail

: "${FLOW_ID:?set FLOW_ID to the id printed by lfx serve}"
: "${LANGFLOW_API_KEY:?set LANGFLOW_API_KEY}"
: "${GOOGLE_ACCESS_TOKEN:?set GOOGLE_ACCESS_TOKEN to a short-lived access token}"

# Bare token: nothing is asserted about expiry or scopes.
curl -sS -X POST "http://localhost:8000/flows/${FLOW_ID}/run" \
  -H "Content-Type: application/json" \
  -H "x-api-key: ${LANGFLOW_API_KEY}" \
  -d "$(jq -n --arg token "${GOOGLE_ACCESS_TOKEN}" '{
        input_value: "describe my connection",
        global_vars: {"LF_CONNECTION__GOOGLE__WORK": $token}
      }')"

# JSON credential: expiry and granted scopes are checked before the provider call,
# so the run fails with auth-expired or scope-missing instead of a provider 401/403.
#
# expires_at is the expiry the injecting system holds for this token, so it is
# computed at send time. A literal timestamp copied from a document is in the past
# by the time anyone runs it, and every request then fails with auth-expired.
curl -sS -X POST "http://localhost:8000/flows/${FLOW_ID}/run" \
  -H "Content-Type: application/json" \
  -H "x-api-key: ${LANGFLOW_API_KEY}" \
  -d "$(jq -n --arg token "${GOOGLE_ACCESS_TOKEN}" \
          --argjson ttl "${GOOGLE_TOKEN_TTL_SECONDS:-3600}" '{
        input_value: "describe my connection",
        global_vars: {
          "LF_CONNECTION__GOOGLE__WORK": ({
            access_token: $token,
            token_type: "Bearer",
            expires_at: (now + $ttl | todate),
            scopes: ["https://www.googleapis.com/auth/drive.readonly"],
            account: {id: "person@example.com"}
          } | tostring)
        }
      }')"

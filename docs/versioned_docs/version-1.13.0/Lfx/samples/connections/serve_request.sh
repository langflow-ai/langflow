#!/usr/bin/env bash
# Supply a connection for one lfx serve request.
#
# global_vars is per-request: it is applied to a deep copy of the graph and bound
# to this request only, so it never becomes an ambient default for the next caller
# on the same warm worker. With the built-in environment resolver, start the
# server with --no-env-fallback to accept credentials only through global_vars.
# Custom resolvers retain their own credential lookup behavior.
set +x # Never trace credential expansion, even when invoked with bash -x.
set -euo pipefail

: "${FLOW_ID:?set FLOW_ID to the id printed by lfx serve}"
: "${LANGFLOW_API_KEY:?set LANGFLOW_API_KEY}"
: "${GOOGLE_ACCESS_TOKEN:?set GOOGLE_ACCESS_TOKEN to a short-lived access token}"
: "${GOOGLE_TOKEN_TTL_SECONDS:?set GOOGLE_TOKEN_TTL_SECONDS to the actual remaining token lifetime}"

# Give each request separate descriptors because reads consume their contents.
# These here-strings use shell builtins; clear exported secrets before starting
# jq or curl so neither their arguments nor their environments carry credentials.
exec 3<<<"x-api-key: ${LANGFLOW_API_KEY}"
exec 4<<<"${GOOGLE_ACCESS_TOKEN}"
exec 5<<<"x-api-key: ${LANGFLOW_API_KEY}"
exec 6<<<"${GOOGLE_ACCESS_TOKEN}"
unset LANGFLOW_API_KEY GOOGLE_ACCESS_TOKEN

# The sample action requires Drive read-only scope. Assert only scopes actually
# granted by the issuer; a bare token fails this action with scope-missing.
jq -n --rawfile token /dev/fd/4 '{
        input_value: "describe my connection",
        global_vars: {
          "LF_CONNECTION__GOOGLE__WORK": ({
            access_token: ($token | rtrimstr("\n")),
            scopes: ["https://www.googleapis.com/auth/drive.readonly"]
          } | tostring)
        }
      }' 3<&- 5<&- 6<&- |
  curl -sS -X POST "http://localhost:8000/flows/${FLOW_ID}/run" \
    -H "Content-Type: application/json" \
    -H @/dev/fd/3 --data-binary @- 4<&- 5<&- 6<&-
exec 3<&- 4<&-

# The TRM blob channel: expiry and scopes are checked before the provider call,
# so the run fails with auth-expired or scope-missing instead of a provider 401/403.
#
# expires_at is the expiry the injecting system holds for this token, so it is
# computed at send time. A literal timestamp copied from a document is in the past
# by the time anyone runs it, and every request then fails with auth-expired.
jq -n --rawfile token /dev/fd/6 \
      --argjson ttl "${GOOGLE_TOKEN_TTL_SECONDS}" '{
        input_value: "describe my connection",
        global_vars: {
          "LANGFLOW_REQUEST_VARIABLES": ({"LF_CONNECTION__GOOGLE__WORK": ({
            access_token: ($token | rtrimstr("\n")),
            token_type: "Bearer",
            expires_at: (now + $ttl | todate),
            scopes: ["https://www.googleapis.com/auth/drive.readonly"],
            account: {id: "person@example.com"}
          } | tostring)} | tostring)
        }
      }' 5<&- |
  curl -sS -X POST "http://localhost:8000/flows/${FLOW_ID}/run" \
    -H "Content-Type: application/json" \
    -H @/dev/fd/5 --data-binary @- 6<&-
exec 5<&- 6<&-

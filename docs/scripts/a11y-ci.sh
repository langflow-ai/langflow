#!/usr/bin/env bash
# Serve the built docs and run the IBM Equal Access checker (npx achecker)
# over representative pages. Fails on any "violation" (see aceconfig.js).
# Used by CI for the light and dark theme scans; run it locally with:
#   npm run build && ./scripts/a11y-ci.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${A11Y_PORT:-3400}"
PAGES=("/" "/get-started-quickstart" "/api-request" "/api")

npm run serve -- --port "$PORT" --no-open >/dev/null 2>&1 &
SERVE_PID=$!
trap 'kill "$SERVE_PID" 2>/dev/null || true' EXIT

for _ in $(seq 1 60); do
  curl -fs "http://localhost:$PORT/" >/dev/null 2>&1 && break
  sleep 1
done

status=0
for page in "${PAGES[@]}"; do
  url="http://localhost:$PORT$page"
  echo "::group::achecker $url"
  if ! npx achecker "$url"; then
    # One retry absorbs rare timing flakes from Redoc's lazy rendering;
    # a real violation fails both attempts.
    echo "Scan failed for $url — retrying once"
    if ! npx achecker "$url"; then
      status=1
    fi
  fi
  echo "::endgroup::"
done

exit $status

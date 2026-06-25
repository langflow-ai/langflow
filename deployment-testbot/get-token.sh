#!/usr/bin/env bash
set -euo pipefail
# Langflow JWT auth: POST /api/v1/login (OAuth2 form-urlencoded) -> {"access_token": "..."}
# Sent as: Authorization: Bearer <token>
U="${LANGFLOW_SUPERUSER:-admin@langflow.test}"
P="${LANGFLOW_SUPERUSER_PASSWORD:-Password123!}"
curl -sf -X POST "http://localhost:8094/api/v1/login" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "username=${U}&password=${P}" \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['access_token'])"

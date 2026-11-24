#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

HOST="${LANGFLOW_HOST:-127.0.0.1}"
PORT="${LANGFLOW_PORT:-7860}"
SUITES="${SUITES:-curl,python,javascript}"
EXECUTE_MODE="${EXECUTE_MODE:-true}"

export LANGFLOW_AUTO_LOGIN="${LANGFLOW_AUTO_LOGIN:-true}"
# /api/v2/workflows (docs Python workflow examples) requires this. Always enable for this
# harness so a user-wide LANGFLOW_DEVELOPER_API_ENABLED=false does not break the suite.
export LANGFLOW_DEVELOPER_API_ENABLED=true

cleanup() {
  if [[ -f /tmp/langflow-server.pid ]]; then
    SERVER_PID="$(< /tmp/langflow-server.pid)"
    if kill -0 "$SERVER_PID" 2>/dev/null; then
      kill "$SERVER_PID" || true
      for _ in {1..15}; do
        if ! kill -0 "$SERVER_PID" 2>/dev/null; then
          break
        fi
        sleep 1
      done
      kill -9 "$SERVER_PID" 2>/dev/null || true
    fi
    rm -f /tmp/langflow-server.pid
  fi
}
trap cleanup EXIT

# If PORT is already taken, Langflow may bind to PORT+1 while this script still uses PORT for
# curl and examples — you then hit the wrong server (e.g. 403 on /api/v2/workflows without dev API).
port_is_in_use() {
  local host="$1" port="$2"
  uv run python - "$host" "$port" <<'PY'
import socket
import sys

host, port = sys.argv[1], int(sys.argv[2])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(0.5)
try:
    sock.connect((host, port))
except (ConnectionRefusedError, TimeoutError, OSError):
    sys.exit(1)
else:
    sys.exit(0)
finally:
    sock.close()
PY
}

pick_free_port() {
  uv run python - "$HOST" <<'PY'
import socket
import sys

host = sys.argv[1]
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind((host, 0))
port = sock.getsockname()[1]
sock.close()
print(port)
PY
}

REQUESTED_PORT="$PORT"
if port_is_in_use "$HOST" "$PORT"; then
  PORT="$(pick_free_port)"
  echo "Port $REQUESTED_PORT was in use; using $PORT for this run (set LANGFLOW_PORT to pin a port)."
fi

echo "Starting Langflow on http://$HOST:$PORT (developer API enabled for /api/v2/workflows)"
# Set on the command line so the server process always sees it (macOS launcher/exec paths).
LANGFLOW_DEVELOPER_API_ENABLED=true uv run langflow run --backend-only --host "$HOST" --port "$PORT" >/tmp/langflow-server.log 2>&1 &
echo $! >/tmp/langflow-server.pid

echo "Waiting for Langflow readiness (DB + services via /health_check)..."
# /health can respond before the Langflow app is fully up (uvicorn default).
for _ in {1..60}; do
  if curl -sf "http://$HOST:$PORT/health_check" >/dev/null; then
    break
  fi
  sleep 2
done

if ! curl -sf "http://$HOST:$PORT/health_check" >/dev/null; then
  echo "Langflow did not become ready in time."
  echo "See /tmp/langflow-server.log for details."
  exit 1
fi

echo "Creating API key for local examples..."
# Use HTTP only: a second process opening the same SQLite DB while the server runs
# causes "database is locked" during Alembic/initialize_services.
export BASE_URL="http://$HOST:$PORT"
LANGFLOW_API_KEY="$(
  uv run python - <<'PY'
import os
import time

import requests
from requests import RequestException

base = os.environ["BASE_URL"]
session = requests.Session()
user = os.environ.get("LANGFLOW_SUPERUSER", "langflow")
password = os.environ.get("LANGFLOW_SUPERUSER_PASSWORD", "langflow")

token = None
last_status = None
# Fail fast: short timeouts and small retry budget.
for attempt in range(1, 9):
    try:
        resp = session.get(f"{base}/api/v1/auto_login", timeout=8)
        last_status = ("auto_login", resp.status_code)
        if resp.status_code == 200:
            token = resp.json()["access_token"]
            break

        resp2 = session.post(
            f"{base}/api/v1/login",
            data={"username": user, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=8,
        )
        last_status = ("login", resp2.status_code)
        if resp2.status_code == 200:
            token = resp2.json()["access_token"]
            break
    except RequestException as exc:
        last_status = ("request_error", str(exc))

    print(f"Auth attempt {attempt}/8 failed: {last_status}", flush=True)
    time.sleep(1)

if not token:
    raise RuntimeError(f"Could not log in after retries (last {last_status})")

key_resp = session.post(
    f"{base}/api/v1/api_key/",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json={"name": "local-docs-examples"},
    timeout=8,
)
key_resp.raise_for_status()
print(key_resp.json()["api_key"])
PY
)"

if [[ -z "$LANGFLOW_API_KEY" ]]; then
  echo "Failed to create API key."
  exit 1
fi

export LANGFLOW_URL="http://$HOST:$PORT"
export LANGFLOW_SERVER_URL="http://$HOST:$PORT"
export LANGFLOW_API_KEY

if [[ "$EXECUTE_MODE" == "true" ]]; then
  echo "Bootstrapping PROJECT_ID/FLOW_ID/FOLDER_ID for examples..."
  BOOTSTRAP_VARS="$(
    uv run python - <<'PY'
import json
import os
import sys
import uuid
from pathlib import Path

import requests

base_url = os.environ["LANGFLOW_URL"]
api_key = os.environ["LANGFLOW_API_KEY"]
headers = {"accept": "application/json", "Content-Type": "application/json", "x-api-key": api_key}

try:
    project_name = f"api-example-project-{uuid.uuid4().hex[:8]}"
    project_resp = requests.post(
        f"{base_url}/api/v1/projects/",
        headers=headers,
        json={"name": project_name, "description": "Local docs examples bootstrap", "components_list": [], "flows_list": []},
        timeout=20,
    )
    project_resp.raise_for_status()
    project_data = project_resp.json()
    project_id = project_data.get("id")
    if not project_id:
        raise RuntimeError(f"Project creation returned no id: {project_data}")

    flow_name = f"api-example-flow-{uuid.uuid4().hex[:8]}"
    flow_resp = requests.post(
        f"{base_url}/api/v1/flows/",
        headers=headers,
        json={
            "name": flow_name,
            "description": "Local docs examples bootstrap",
            "data": {"nodes": [], "edges": []},
        },
        timeout=20,
    )
    flow_resp.raise_for_status()
    flow_data = flow_resp.json()
    flow_id = flow_data.get("id")
    if not flow_id:
        raise RuntimeError(f"Flow creation returned no id: {flow_data}")

    build_resp = requests.post(
        f"{base_url}/api/v1/build/{flow_id}/flow",
        headers=headers,
        json={},
        timeout=20,
    )
    build_resp.raise_for_status()
    build_data = build_resp.json()
    job_id = build_data.get("job_id")
    if not job_id:
        raise RuntimeError(f"Build start returned no job_id: {build_data}")

    project_zip_path = Path("/tmp/langflow-project-import.zip")
    try:
        export_resp = requests.get(
            f"{base_url}/api/v1/projects/download/{project_id}",
            headers={"accept": "application/json", "x-api-key": api_key},
            timeout=30,
        )
        export_resp.raise_for_status()
        project_zip_path.write_bytes(export_resp.content)
    except Exception:
        # Keep bootstrap resilient; some local instances can fail project export.
        project_zip_path = Path("docs/docs/API-Reference/fixtures/project-import.zip")

    # Many examples use FOLDER_ID and PROJECT_ID interchangeably for project-scoped routes.
    print(f"PROJECT_ID={project_id}")
    print(f"FOLDER_ID={project_id}")
    print(f"FLOW_ID={flow_id}")
    print(f"JOB_ID={job_id}")
    print(f"PROJECT_IMPORT_FILE={project_zip_path}")
except Exception as exc:
    print(f"ERROR={exc}", file=sys.stderr)
    raise
PY
  )"

  while IFS='=' read -r key value; do
    if [[ -n "$key" && -n "$value" ]]; then
      export "$key=$value"
    fi
  done <<< "$BOOTSTRAP_VARS"

  echo "Using PROJECT_ID=$PROJECT_ID FLOW_ID=$FLOW_ID FOLDER_ID=$FOLDER_ID"
fi

EXAMPLE_MODE_ARGS=""
if [[ "$EXECUTE_MODE" == "true" ]]; then
  EXAMPLE_MODE_ARGS="--execute"
fi

echo "Running suites: $SUITES (execute=$EXECUTE_MODE)"
IFS=',' read -ra SUITE_LIST <<< "$SUITES"
for suite in "${SUITE_LIST[@]}"; do
  suite="$(echo "$suite" | xargs)"
  case "$suite" in
    curl)
      bash docs/docs/API-Reference/curl-examples/test-curl-examples.sh $EXAMPLE_MODE_ARGS
      ;;
    python)
      bash docs/docs/API-Reference/python-examples/test-python-examples.sh $EXAMPLE_MODE_ARGS
      ;;
    javascript)
      bash docs/docs/API-Reference/javascript-examples/test-javascript-examples.sh $EXAMPLE_MODE_ARGS
      ;;
    "")
      ;;
    *)
      echo "Unknown suite: '$suite'. Valid values: curl, python, javascript"
      exit 1
      ;;
  esac
done

echo "Done. Server log: /tmp/langflow-server.log"

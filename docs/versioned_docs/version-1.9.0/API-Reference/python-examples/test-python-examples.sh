#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
EXAMPLES_DIR="$SCRIPT_DIR"
TEST_SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"

MODE="syntax"

load_repo_env() {
  local env_file="$ROOT_DIR/.env"
  if [[ -f "$env_file" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$env_file"
    set +a
  fi
}

print_help() {
  cat <<'EOF'
Usage:
  test-python-examples.sh [--execute]

Modes:
  (default)            Syntax check only (py_compile)
  --execute            Execute examples after syntax checks

EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute)
      MODE="execute"
      shift
      ;;
    --help|-h)
      print_help
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      print_help
      exit 1
      ;;
  esac
done

PY_FILES=()
while IFS= read -r line; do
  if [[ "$(basename "$line")" == "$TEST_SCRIPT_NAME" ]]; then
    continue
  fi
  PY_FILES+=("$line")
done < <(uv run python - "$EXAMPLES_DIR" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
for p in sorted(root.rglob("*.py")):
    print(p)
PY
)

if [[ ${#PY_FILES[@]} -eq 0 ]]; then
  echo "No .py examples found in $EXAMPLES_DIR"
  exit 1
fi

PASS=0
FAIL=0
SKIP=0
PY_TIMEOUT_SECONDS="${PY_TIMEOUT_SECONDS:-45}"

echo "Testing ${#PY_FILES[@]} Python examples in '$MODE' mode..."
if [[ "$MODE" == "execute" ]]; then
  load_repo_env
fi

has_placeholder_file_inputs() {
  uv run python - "$1" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read()
needles = ("FILE_NAME", "PATH/TO/FILE", "<file contents>")
print("yes" if any(n in text for n in needles) else "no")
PY
}

has_missing_required_env() {
  uv run python - "$1" <<'PY'
import os
import re
import sys

text = open(sys.argv[1], encoding="utf-8").read()
vars_to_check = ["FLOW_ID", "PROJECT_ID", "FOLDER_ID", "SESSION_ID", "JOB_ID", "USER_ID"]

for name in vars_to_check:
    getenv_pat = rf"os\.getenv\(\s*['\"]{name}['\"]"
    environ_pat = rf"os\.environ\.get\(\s*['\"]{name}['\"]"
    if (re.search(getenv_pat, text) or re.search(environ_pat, text)) and not os.getenv(name):
        print(name)
        raise SystemExit(0)

print("")
PY
}

print_failure_logs() {
  local out_file="$1"
  local err_file="$2"
  if [[ -s "$err_file" ]]; then
    echo "      stderr (last 12 lines):"
    uv run python - "$err_file" <<'PY'
import sys
from pathlib import Path

lines = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
for line in lines[-12:]:
    print(line)
PY
  fi
  if [[ -s "$out_file" ]]; then
    echo "      stdout (last 12 lines):"
    uv run python - "$out_file" <<'PY'
import sys
from pathlib import Path

lines = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
for line in lines[-12:]:
    print(line)
PY
  fi
}

for file in "${PY_FILES[@]}"; do
  rel="${file#"$ROOT_DIR"/}"

  if ! uv run python -m py_compile "$file"; then
    echo "FAIL  $rel (py_compile)"
    ((FAIL+=1))
    continue
  fi

  if [[ "$MODE" == "execute" ]]; then
    # api-openai-responses/* call Langflow's HTTP API (e.g. /api/v1/responses) with x-api-key;
    # they do not require OPENAI_API_KEY in the environment (same as the JS examples).

    # Streaming / long-running examples: skip in local harness (hang, flaky, or need extra setup).
    case "$(basename "$file")" in
      build-flow-and-stream-events-2.py|build-flow-and-stream-events-3.py|stream-llm-token-responses.py|example-streaming-request.py|stream-logs.py)
        echo "SKIP  $rel (streaming/long-running; not run in local harness)"
        ((SKIP+=1))
        continue
        ;;
    esac

    if [[ "$(basename "$file")" == "retrieve-logs-with-optional-parameters.py" ]]; then
      echo "SKIP  $rel (/logs endpoint not implemented in local server)"
      ((SKIP+=1))
      continue
    fi

    if [[ "$(basename "$file")" == "reset-password.py" ]]; then
      echo "SKIP  $rel (reset-password may return 500 in local SQLite runs; run manually if needed)"
      ((SKIP+=1))
      continue
    fi

    if [[ -z "${LANGFLOW_API_KEY:-}" || ( -z "${LANGFLOW_URL:-}" && -z "${LANGFLOW_SERVER_URL:-}" ) ]]; then
      echo "SKIP  $rel (set LANGFLOW_API_KEY and LANGFLOW_URL or LANGFLOW_SERVER_URL to execute)"
      ((SKIP+=1))
      continue
    fi

    if [[ "$(has_placeholder_file_inputs "$file")" == "yes" ]]; then
      echo "SKIP  $rel (placeholder file input values)"
      ((SKIP+=1))
      continue
    fi

    missing_env="$(has_missing_required_env "$file")"
    if [[ -n "$missing_env" ]]; then
      echo "SKIP  $rel (missing required env: $missing_env)"
      ((SKIP+=1))
      continue
    fi

    if ! uv run python - "$file" "$PY_TIMEOUT_SECONDS" >/tmp/langflow-python-example.out 2>/tmp/langflow-python-example.err <<'PY'
import runpy
import signal
import sys

script_path = sys.argv[1]
timeout_seconds = int(sys.argv[2])

def _handle_timeout(_signum, _frame):
    raise TimeoutError(f"execution timed out after {timeout_seconds}s")

signal.signal(signal.SIGALRM, _handle_timeout)
signal.alarm(timeout_seconds)
try:
    runpy.run_path(script_path, run_name="__main__")
finally:
    signal.alarm(0)
PY
    then
      echo "FAIL  $rel (execution)"
      print_failure_logs "/tmp/langflow-python-example.out" "/tmp/langflow-python-example.err"
      ((FAIL+=1))
      continue
    fi
  fi

  echo "PASS  $rel"
  ((PASS+=1))
done

echo
echo "Summary: PASS=$PASS FAIL=$FAIL SKIP=$SKIP TOTAL=${#PY_FILES[@]}"

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi

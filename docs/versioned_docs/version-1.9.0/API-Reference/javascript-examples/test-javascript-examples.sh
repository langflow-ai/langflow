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
  test-javascript-examples.sh [--execute]

Modes:
  (default)            Syntax check only (`node --check`)
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

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is required to test JavaScript examples."
  exit 1
fi

JS_FILES=()
while IFS= read -r line; do
  if [[ "$(basename "$line")" == "$TEST_SCRIPT_NAME" ]]; then
    continue
  fi
  JS_FILES+=("$line")
done < <(python3 - "$EXAMPLES_DIR" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
for p in sorted(root.rglob("*.js")):
    print(p)
PY
)

if [[ ${#JS_FILES[@]} -eq 0 ]]; then
  echo "No .js examples found in $EXAMPLES_DIR"
  exit 1
fi

PASS=0
FAIL=0
SKIP=0

echo "Testing ${#JS_FILES[@]} JavaScript examples in '$MODE' mode..."
if [[ "$MODE" == "execute" ]]; then
  load_repo_env
fi

has_placeholder_file_inputs() {
  python3 - "$1" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read()
needles = ("FILE_NAME", "PATH/TO/FILE", "<file contents>")
print("yes" if any(n in text for n in needles) else "no")
PY
}

has_missing_required_env() {
  python3 - "$1" <<'PY'
import os
import re
import sys

text = open(sys.argv[1], encoding="utf-8").read()
vars_to_check = ["FLOW_ID", "PROJECT_ID", "FOLDER_ID", "SESSION_ID", "JOB_ID", "USER_ID"]

for name in vars_to_check:
    if re.search(rf"process\.env\.{name}\b", text) and not os.getenv(name):
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
    python3 - "$err_file" <<'PY'
import sys
from pathlib import Path

lines = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
for line in lines[-12:]:
    print(line)
PY
  fi
  if [[ -s "$out_file" ]]; then
    echo "      stdout (last 12 lines):"
    python3 - "$out_file" <<'PY'
import sys
from pathlib import Path

lines = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
for line in lines[-12:]:
    print(line)
PY
  fi
}

for file in "${JS_FILES[@]}"; do
  rel="${file#"$ROOT_DIR"/}"

  if ! node --check "$file" >/tmp/langflow-js-check.out 2>/tmp/langflow-js-check.err; then
    echo "FAIL  $rel (node --check)"
    ((FAIL+=1))
    continue
  fi

  if [[ "$MODE" == "execute" ]]; then
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

    if ! node "$file" >/tmp/langflow-js-example.out 2>/tmp/langflow-js-example.err; then
      echo "FAIL  $rel (execution)"
      print_failure_logs "/tmp/langflow-js-example.out" "/tmp/langflow-js-example.err"
      ((FAIL+=1))
      continue
    fi
  fi

  echo "PASS  $rel"
  ((PASS+=1))
done

echo
echo "Summary: PASS=$PASS FAIL=$FAIL SKIP=$SKIP TOTAL=${#JS_FILES[@]}"

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi

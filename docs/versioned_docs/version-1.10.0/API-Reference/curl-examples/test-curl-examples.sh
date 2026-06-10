#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

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
  test-curl-examples.sh [--execute]

Modes:
  (default)            Syntax check only (bash -n)
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

if [[ ! -d "$EXAMPLES_DIR" ]]; then
  echo "Examples directory not found: $EXAMPLES_DIR"
  exit 1
fi

SH_FILES=()
while IFS= read -r line; do
  if [[ "$line" == "$SCRIPT_DIR/$TEST_SCRIPT_NAME" ]]; then
    continue
  fi
  SH_FILES+=("$line")
done < <(python3 - "$EXAMPLES_DIR" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
for p in sorted(root.rglob("*.sh")):
    print(p)
PY
)

if [[ ${#SH_FILES[@]} -eq 0 ]]; then
  echo "No .sh examples found in $EXAMPLES_DIR"
  exit 1
fi

PASS=0
FAIL=0
SKIP=0

echo "Testing ${#SH_FILES[@]} curl shell examples in '$MODE' mode..."
if [[ "$MODE" == "execute" ]]; then
  load_repo_env
fi

has_missing_required_env() {
  python3 - "$1" <<'PY'
import os
import re
import sys

text = open(sys.argv[1], encoding="utf-8").read()
vars_to_check = ["FLOW_ID", "PROJECT_ID", "FOLDER_ID", "SESSION_ID", "JOB_ID", "USER_ID"]

for name in vars_to_check:
    if re.search(rf'\$\{{?{name}\}}?', text) and not os.getenv(name):
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

for file in "${SH_FILES[@]}"; do
  rel="${file#"$ROOT_DIR"/}"

  if ! bash -n "$file"; then
    echo "FAIL  $rel (bash -n)"
    ((FAIL+=1))
    continue
  fi

  if [[ "$MODE" == "execute" ]]; then
    if [[ -z "${LANGFLOW_API_KEY:-}" || ( -z "${LANGFLOW_URL:-}" && -z "${LANGFLOW_SERVER_URL:-}" ) ]]; then
      echo "SKIP  $rel (set LANGFLOW_API_KEY and LANGFLOW_URL or LANGFLOW_SERVER_URL to execute)"
      ((SKIP+=1))
      continue
    fi

    missing_env="$(has_missing_required_env "$file")"
    if [[ -n "$missing_env" ]]; then
      echo "SKIP  $rel (missing required env: $missing_env)"
      ((SKIP+=1))
      continue
    fi

    if ! bash "$file" >/tmp/langflow-curl-example.out 2>/tmp/langflow-curl-example.err; then
      echo "FAIL  $rel (execution)"
      print_failure_logs "/tmp/langflow-curl-example.out" "/tmp/langflow-curl-example.err"
      ((FAIL+=1))
      continue
    fi
  fi

  echo "PASS  $rel"
  ((PASS+=1))
done

echo
echo "Summary: PASS=$PASS FAIL=$FAIL SKIP=$SKIP TOTAL=${#SH_FILES[@]}"

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi

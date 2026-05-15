#!/usr/bin/env bash
# Run the multitenant lfx prototype end-to-end.
#
# Orchestrator boots the Runtime API, seeds OPENAI_API_KEY, mints a
# scope-bound run token, then spawns an lfx worker subprocess whose env
# has been scrubbed of every DB and provider credential. The worker runs
# the real Basic Prompting flow JSON through real lfx, resolving the
# api_key through the capability-backed VariableService.
#
# Usage:
#   bash scripts/run.sh           # happy path
#   bash scripts/run.sh --deny    # mint with no scopes; expect refusal
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Syncing python deps"
uv sync --quiet
export PATH="$(pwd)/.venv/bin:${PATH}"

uv run python scripts/orchestrator.py "$@"

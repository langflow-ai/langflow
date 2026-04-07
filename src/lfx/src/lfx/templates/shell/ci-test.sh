#!/usr/bin/env bash
# ci-test.sh
#
# PURPOSE
#   Run pytest flow-integration tests against a live Langflow instance
#   using the langflow-sdk `flow_runner` fixture.
#
# USAGE
#   chmod +x ci-test.sh
#   ./ci-test.sh
#
# ENVIRONMENT VARIABLES — connection (pick one approach)
#
#   Approach A: direct URL + key (simplest)
#     LANGFLOW_URL        URL of the target Langflow instance.
#                         e.g. https://staging.langflow.example.com
#     LANGFLOW_API_KEY    API key for that instance.
#
#   Approach B: named environment from a TOML config
#     LANGFLOW_ENV                 Name of the environment block in the TOML.
#                                  e.g. staging
#     LANGFLOW_ENVIRONMENTS_FILE   Path to the environments TOML.
#                                  Default: langflow-environments.toml
#     <api_key_env var>            The env var named in api_key_env inside the
#                                  TOML block, e.g. LANGFLOW_STAGING_API_KEY.
#
#   The TOML format (see also ci-push.sh):
#
#     [environments.staging]
#     url        = "https://staging.langflow.example.com"
#     api_key_env = "LANGFLOW_STAGING_API_KEY"
#
# ENVIRONMENT VARIABLES — behaviour
#   TESTS_DIR        Directory containing test files.  Default: tests/
#   PYTEST_MARKERS   Markers to pass to -m.  Default: integration
#   PYTEST_ARGS      Extra arguments forwarded verbatim to pytest.
#   SDK_VERSION      langflow-sdk PEP 508 version specifier suffix appended
#                    directly to the package name, e.g. ">=0.4,<1" or "==1.2.3".
#                    Default: installs latest.
#
# SKIPPING
#   When neither LANGFLOW_URL nor LANGFLOW_ENV is set the tests auto-skip
#   (the flow_runner fixture detects no connection).  This means the script
#   exits 0 even when run on a branch that lacks the necessary secrets.
#
# EXIT CODES
#   0  All tests passed (or skipped due to missing connection)
#   1  One or more tests failed
#
# INTEGRATIONS
#   Jenkins:          sh 'ci-test.sh'
#   CircleCI:         - run: bash ci-test.sh
#   Bitbucket:        - bash ci-test.sh
#   Azure Pipelines:  - script: bash ci-test.sh

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────── #

TESTS_DIR="${TESTS_DIR:-tests/}"
PYTEST_MARKERS="${PYTEST_MARKERS:-integration}"
PYTEST_ARGS="${PYTEST_ARGS:-}"
SDK_VERSION="${SDK_VERSION:-}"
LANGFLOW_ENV="${LANGFLOW_ENV:-}"
LANGFLOW_ENVIRONMENTS_FILE="${LANGFLOW_ENVIRONMENTS_FILE:-langflow-environments.toml}"

# ── Install dependencies ───────────────────────────────────────────────────── #

# Normalise SDK_VERSION: if it looks like a bare version (starts with a digit),
# prepend "==" so the pip specifier is valid.
if [[ -n "${SDK_VERSION}" && "${SDK_VERSION}" =~ ^[0-9] ]]; then
  SDK_VERSION="==${SDK_VERSION}"
fi

echo "==> Installing langflow-sdk[testing] and pytest ..."
pip install --quiet \
  "langflow-sdk[testing]${SDK_VERSION}" \
  pytest

# ── Build environments file if using Approach B ───────────────────────────── #

if [[ -n "${LANGFLOW_ENV}" && ! -f "${LANGFLOW_ENVIRONMENTS_FILE}" ]]; then
  # Derive variable names from the env name (uppercased, hyphens → underscores)
  ENV_UPPER="${LANGFLOW_ENV^^}"
  ENV_UPPER="${ENV_UPPER//-/_}"
  URL_VAR="LANGFLOW_${ENV_UPPER}_URL"
  KEY_VAR="LANGFLOW_${ENV_UPPER}_API_KEY"

  echo "==> Writing ${LANGFLOW_ENVIRONMENTS_FILE} for environment '${LANGFLOW_ENV}' ..."
  printf '[environments.%s]\nurl = "%s"\napi_key_env = "%s"\n' \
    "${LANGFLOW_ENV}" \
    "${!URL_VAR:-}" \
    "${KEY_VAR}" \
    > "${LANGFLOW_ENVIRONMENTS_FILE}"
fi

# ── Run tests ─────────────────────────────────────────────────────────────── #

# Build pytest command
PYTEST_CMD=(pytest "${TESTS_DIR}" -v --tb=short)

if [[ -n "${PYTEST_MARKERS}" ]]; then
  PYTEST_CMD+=(-m "${PYTEST_MARKERS}")
fi

if [[ -n "${LANGFLOW_ENV}" ]]; then
  PYTEST_CMD+=(--langflow-env "${LANGFLOW_ENV}")
  export LANGFLOW_ENVIRONMENTS_FILE
elif [[ -n "${LANGFLOW_URL:-}" ]]; then
  PYTEST_CMD+=(--langflow-url "${LANGFLOW_URL}")
  [[ -n "${LANGFLOW_API_KEY:-}" ]] && PYTEST_CMD+=(--langflow-api-key "${LANGFLOW_API_KEY}")
fi

# Append any extra user-supplied args
# shellcheck disable=SC2206
[[ -n "${PYTEST_ARGS}" ]] && PYTEST_CMD+=(${PYTEST_ARGS})

echo "==> Running: ${PYTEST_CMD[*]}"
"${PYTEST_CMD[@]}"

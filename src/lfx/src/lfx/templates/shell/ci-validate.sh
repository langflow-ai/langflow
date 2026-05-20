#!/usr/bin/env bash
# ci-validate.sh
#
# PURPOSE
#   Validate all Langflow flow JSON files using `lfx validate`.
#   No secrets or network access required — pure static analysis.
#
# USAGE
#   chmod +x ci-validate.sh
#   ./ci-validate.sh
#
# ENVIRONMENT VARIABLES
#   FLOWS_DIR        Directory containing flow JSON files.
#                    Default: flows/
#   VALIDATE_LEVEL   Depth of validation (1–4).  Level 4 checks structure,
#                    components, edge types, AND required inputs.
#                    Default: 4
#   VALIDATE_FORMAT  Output format: text | json.
#                    Default: text
#   LFX_VERSION      lfx PEP 508 version specifier suffix appended directly
#                    to the package name, e.g. ">=0.4,<1" or "==1.2.3".
#                    Default: installs latest.
#
# EXIT CODES
#   0  All flows valid
#   1  One or more flows failed validation
#   2  Flow file / directory not found
#
# INTEGRATIONS
#   Jenkins:          sh 'ci-validate.sh'
#   CircleCI:         - run: bash ci-validate.sh
#   Bitbucket:        - bash ci-validate.sh
#   Azure Pipelines:  - script: bash ci-validate.sh
#   Generic:          bash ci-validate.sh

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────── #

FLOWS_DIR="${FLOWS_DIR:-flows/}"
VALIDATE_LEVEL="${VALIDATE_LEVEL:-4}"
VALIDATE_FORMAT="${VALIDATE_FORMAT:-text}"
LFX_VERSION="${LFX_VERSION:-}"

# Normalise LFX_VERSION: if it looks like a bare version (starts with a digit),
# prepend "==" so the pip specifier is valid.
if [[ -n "${LFX_VERSION}" && "${LFX_VERSION}" =~ ^[0-9] ]]; then
  LFX_VERSION="==${LFX_VERSION}"
fi

# ── Install lfx ───────────────────────────────────────────────────────────── #

echo "==> Installing lfx${LFX_VERSION:+ ${LFX_VERSION}} ..."
pip install --quiet "lfx${LFX_VERSION}"

# ── Validate ──────────────────────────────────────────────────────────────── #

echo "==> Validating flows in ${FLOWS_DIR} (level ${VALIDATE_LEVEL}) ..."
lfx validate "${FLOWS_DIR}" \
  --level "${VALIDATE_LEVEL}" \
  --format "${VALIDATE_FORMAT}"

echo "==> All flows valid."

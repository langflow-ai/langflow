#!/usr/bin/env bash
# Bootstrap a local Ollama server with the granite3.3:2b model so that
# `make run_cli` exposes a pre-configured Ollama provider in Langflow.
#
# Resolution order:
#   1. If something already responds on $OLLAMA_PORT, use it.
#   2. Else if a container engine (docker or podman) is available with a
#      running daemon, start (or restart) a container named `langflow-ollama`
#      and pull the model.
#   3. Else if the `ollama` CLI is installed, start `ollama serve` in the
#      background and pull the model.
#   4. Else, on macOS with Homebrew, install Ollama via `brew install ollama`,
#      then go to step 3. Skip this with LANGFLOW_OLLAMA_NO_INSTALL=1.
#   5. Else, fail with explicit installation instructions.
#
# Environment variables:
#   OLLAMA_PORT                 default 11434
#   OLLAMA_HOST                 default 127.0.0.1
#   LANGFLOW_OLLAMA_MODEL       default granite3.3:2b
#   LANGFLOW_OLLAMA_ENGINE      override container engine: docker | podman
#                               (auto-detected when unset)
#   LANGFLOW_OLLAMA_NO_INSTALL  set to 1 to disable brew autoinstall
#   LANGFLOW_OLLAMA_OPTIONAL    set to 1 to make this script never exit non-zero
#                               (useful for CI / contributors who do not need
#                                the bundled provider)

set -euo pipefail

OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1}"
OLLAMA_MODEL="${LANGFLOW_OLLAMA_MODEL:-granite3.3:2b}"
CONTAINER_NAME="langflow-ollama"
VOLUME_NAME="langflow-ollama-data"
HEALTH_TIMEOUT_S=60

# Resolved container engine (docker | podman). Empty means "no engine usable".
ENGINE=""

log()  { printf '\033[1;36m[ollama-bootstrap]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[ollama-bootstrap]\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31m[ollama-bootstrap]\033[0m %s\n' "$*" >&2; }

abort() {
  err "$*"
  if [ "${LANGFLOW_OLLAMA_OPTIONAL:-0}" = "1" ]; then
    warn "LANGFLOW_OLLAMA_OPTIONAL=1 — continuing without Ollama (provider will be unreachable)."
    exit 0
  fi
  exit 1
}

is_server_up() {
  curl -fsS --max-time 2 "http://${OLLAMA_HOST}:${OLLAMA_PORT}/api/tags" >/dev/null 2>&1
}

wait_for_server() {
  local elapsed=0
  while ! is_server_up; do
    if [ "$elapsed" -ge "$HEALTH_TIMEOUT_S" ]; then
      return 1
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
}

engine_is_usable() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 && "$cmd" info >/dev/null 2>&1
}

resolve_engine() {
  if [ -n "${LANGFLOW_OLLAMA_ENGINE:-}" ]; then
    if engine_is_usable "$LANGFLOW_OLLAMA_ENGINE"; then
      ENGINE="$LANGFLOW_OLLAMA_ENGINE"
      return 0
    fi
    warn "LANGFLOW_OLLAMA_ENGINE='${LANGFLOW_OLLAMA_ENGINE}' is not usable — falling back to auto-detect."
  fi
  for candidate in docker podman; do
    if engine_is_usable "$candidate"; then
      ENGINE="$candidate"
      return 0
    fi
  done
  return 1
}

ensure_model_engine() {
  log "Ensuring model '${OLLAMA_MODEL}' is pulled (${ENGINE} exec)..."
  if "$ENGINE" exec "$CONTAINER_NAME" ollama list 2>/dev/null \
      | awk 'NR>1 {print $1}' | grep -Fxq "$OLLAMA_MODEL"; then
    log "Model '${OLLAMA_MODEL}' already present."
    return 0
  fi
  "$ENGINE" exec "$CONTAINER_NAME" ollama pull "$OLLAMA_MODEL"
}

ensure_model_local() {
  log "Ensuring model '${OLLAMA_MODEL}' is pulled (local ollama CLI)..."
  if ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -Fxq "$OLLAMA_MODEL"; then
    log "Model '${OLLAMA_MODEL}' already present."
    return 0
  fi
  ollama pull "$OLLAMA_MODEL"
}

start_with_engine() {
  log "Starting Ollama container '${CONTAINER_NAME}' on port ${OLLAMA_PORT} (engine: ${ENGINE})..."
  if "$ENGINE" ps --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"; then
    log "Container already running."
  elif "$ENGINE" ps -a --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"; then
    log "Container exists but is stopped — restarting."
    "$ENGINE" start "$CONTAINER_NAME" >/dev/null
  else
    "$ENGINE" volume create "$VOLUME_NAME" >/dev/null 2>&1 || true
    "$ENGINE" run -d \
      --name "$CONTAINER_NAME" \
      --restart unless-stopped \
      -p "${OLLAMA_PORT}:11434" \
      -v "${VOLUME_NAME}:/root/.ollama" \
      docker.io/ollama/ollama:latest >/dev/null
  fi
  if ! wait_for_server; then
    abort "Ollama container did not become healthy within ${HEALTH_TIMEOUT_S}s. Inspect with: ${ENGINE} logs ${CONTAINER_NAME}"
  fi
  ensure_model_engine
}

start_with_local_cli() {
  log "Starting local 'ollama serve' on port ${OLLAMA_PORT} (logs: /tmp/langflow-ollama.log)..."
  OLLAMA_HOST="${OLLAMA_HOST}:${OLLAMA_PORT}" nohup ollama serve >/tmp/langflow-ollama.log 2>&1 &
  if ! wait_for_server; then
    abort "Local 'ollama serve' did not become healthy within ${HEALTH_TIMEOUT_S}s. Tail /tmp/langflow-ollama.log for details."
  fi
  ensure_model_local
}

try_install_ollama() {
  if [ "${LANGFLOW_OLLAMA_NO_INSTALL:-0}" = "1" ]; then
    return 1
  fi
  case "$(uname -s)" in
    Darwin)
      if command -v brew >/dev/null 2>&1; then
        log "Ollama not found — installing via Homebrew (brew install ollama)..."
        brew install ollama
        return 0
      fi
      ;;
  esac
  return 1
}

main() {
  if is_server_up; then
    log "Ollama already responding at http://${OLLAMA_HOST}:${OLLAMA_PORT} — skipping bootstrap."
    log "(If '${OLLAMA_MODEL}' is not installed, run: ollama pull ${OLLAMA_MODEL})"
    return 0
  fi

  if resolve_engine; then
    start_with_engine
  elif command -v ollama >/dev/null 2>&1; then
    start_with_local_cli
  elif try_install_ollama && command -v ollama >/dev/null 2>&1; then
    start_with_local_cli
  else
    abort "Cannot start Ollama: no usable container engine (docker / podman) and no 'ollama' CLI.
       Install one of:
         - Podman:          https://podman.io/docs/installation  (then 'podman machine start')
         - Docker Desktop:  https://docs.docker.com/get-docker/
         - Ollama:          https://ollama.com/download           (or 'brew install ollama')
       Then re-run 'make run_cli'.
       To skip this bootstrap on this machine, run:  LANGFLOW_OLLAMA_OPTIONAL=1 make run_cli"
  fi

  log "Ollama is up at http://${OLLAMA_HOST}:${OLLAMA_PORT} with model '${OLLAMA_MODEL}'."
}

main "$@"

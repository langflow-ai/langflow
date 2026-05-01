#!/usr/bin/env bash
# Bootstrap a local Ollama server with the granite3.3:2b model so that
# `make run_cli` exposes a pre-configured Ollama provider in Langflow.
#
# Behavior:
#   - If something is already responding on $OLLAMA_PORT, do nothing.
#   - Else if `docker` is available, start (or restart) a container named
#     `langflow-ollama` and pull granite3.3:2b on it.
#   - Else if the `ollama` CLI is installed locally, start `ollama serve`
#     in the background and pull the model.
#   - Else print a warning and exit 0 (Langflow still starts; Ollama provider
#     just won't be reachable).
#
# Exits non-zero only when an explicit step fails (docker run/exec, ollama pull).

set -euo pipefail

OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1}"
OLLAMA_MODEL="${LANGFLOW_OLLAMA_MODEL:-granite3.3:2b}"
CONTAINER_NAME="langflow-ollama"
VOLUME_NAME="langflow-ollama-data"
HEALTH_TIMEOUT_S=60

log()  { printf '\033[1;36m[ollama-bootstrap]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[ollama-bootstrap]\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31m[ollama-bootstrap]\033[0m %s\n' "$*" >&2; }

is_server_up() {
  curl -fsS --max-time 2 "http://${OLLAMA_HOST}:${OLLAMA_PORT}/api/tags" >/dev/null 2>&1
}

wait_for_server() {
  local elapsed=0
  while ! is_server_up; do
    if [ "$elapsed" -ge "$HEALTH_TIMEOUT_S" ]; then
      err "Ollama did not become healthy within ${HEALTH_TIMEOUT_S}s"
      return 1
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
}

ensure_model_docker() {
  log "Ensuring model '${OLLAMA_MODEL}' is pulled (docker exec)..."
  if docker exec "$CONTAINER_NAME" ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -Fxq "$OLLAMA_MODEL"; then
    log "Model '${OLLAMA_MODEL}' already present."
    return 0
  fi
  docker exec "$CONTAINER_NAME" ollama pull "$OLLAMA_MODEL"
}

ensure_model_local() {
  log "Ensuring model '${OLLAMA_MODEL}' is pulled (local ollama CLI)..."
  if ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -Fxq "$OLLAMA_MODEL"; then
    log "Model '${OLLAMA_MODEL}' already present."
    return 0
  fi
  ollama pull "$OLLAMA_MODEL"
}

start_with_docker() {
  log "Starting Ollama container '${CONTAINER_NAME}' on port ${OLLAMA_PORT}..."
  if docker ps --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"; then
    log "Container already running."
  elif docker ps -a --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"; then
    log "Container exists but is stopped — restarting."
    docker start "$CONTAINER_NAME" >/dev/null
  else
    docker volume create "$VOLUME_NAME" >/dev/null
    docker run -d \
      --name "$CONTAINER_NAME" \
      --restart unless-stopped \
      -p "${OLLAMA_PORT}:11434" \
      -v "${VOLUME_NAME}:/root/.ollama" \
      ollama/ollama >/dev/null
  fi
  wait_for_server
  ensure_model_docker
}

start_with_local_cli() {
  log "Starting local 'ollama serve' on port ${OLLAMA_PORT}..."
  OLLAMA_HOST="${OLLAMA_HOST}:${OLLAMA_PORT}" nohup ollama serve >/tmp/langflow-ollama.log 2>&1 &
  wait_for_server
  ensure_model_local
}

main() {
  if is_server_up; then
    log "Ollama already responding at http://${OLLAMA_HOST}:${OLLAMA_PORT} — skipping bootstrap."
    log "(If granite3.3:2b is not installed, run: ollama pull ${OLLAMA_MODEL})"
    return 0
  fi

  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    start_with_docker
  elif command -v ollama >/dev/null 2>&1; then
    start_with_local_cli
  else
    warn "Neither Docker nor the 'ollama' CLI is available."
    warn "Langflow will start, but the Ollama provider won't be reachable."
    warn "Install Docker (https://docs.docker.com/get-docker/) or Ollama (https://ollama.com/download) and re-run."
    return 0
  fi

  log "Ollama is up at http://${OLLAMA_HOST}:${OLLAMA_PORT} with model '${OLLAMA_MODEL}'."
}

main "$@"

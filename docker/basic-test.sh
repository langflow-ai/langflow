#!/usr/bin/env bash
# =============================================================================
# Langflow Quick Test Script
#
# This script provides a simple way to start the Langflow stack for testing,
# without requiring Docker Compose. It handles network creation,
# container lifecycle management, and proper error handling.
#
# Author: Patryk Golabek
# =============================================================================

set -eo pipefail

# ANSI color codes for better readability
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[0;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Configuration - can be overridden by environment variables
: "${BACKEND_PORT:=7860}"
: "${FRONTEND_PORT:=8080}"
: "${BACKEND_IMAGE:=langflow_backend:latest}"
: "${FRONTEND_IMAGE:=langflow_frontend:latest}"
: "${NETWORK_NAME:=langflow_network}"
: "${ENV_FILE:=.env}"
: "${HEALTH_CHECK_TIMEOUT:=30}" # In seconds

# Runtime variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_CONTAINER_NAME="langflow-backend"
FRONTEND_CONTAINER_NAME="langflow-frontend"
LOG_PREFIX="[$(date +%Y-%m-%d\ %H:%M:%S)]"

# =============================================================================
# Utility functions
# =============================================================================

log() {
  echo -e "${LOG_PREFIX} $1"
}

log_info() {
  log "${BLUE}INFO${NC}: $1"
}

log_success() {
  log "${GREEN}SUCCESS${NC}: $1"
}

log_warning() {
  log "${YELLOW}WARNING${NC}: $1"
}

log_error() {
  log "${RED}ERROR${NC}: $1" >&2
}

show_help() {
  cat << EOF
Usage: $(basename "$0") [options]

Options:
  -h, --help                 Display this help message
  -b, --backend-port PORT    Backend port (default: $BACKEND_PORT)
  -f, --frontend-port PORT   Frontend port (default: $FRONTEND_PORT)
  --backend-image IMAGE      Backend Docker image (default: $BACKEND_IMAGE)
  --frontend-image IMAGE     Frontend Docker image (default: $FRONTEND_IMAGE)
  -e, --env-file FILE        Environment file path (default: $ENV_FILE)
  -n, --network NAME         Docker network name (default: $NETWORK_NAME)
  --timeout SECONDS          Health check timeout in seconds (default: $HEALTH_CHECK_TIMEOUT)

Example:
  $(basename "$0") --backend-port 7861 --frontend-port 8081 --env-file custom.env

EOF
}

cleanup_container() {
  local container_name=$1

  if docker ps -a --format "{{.Names}}" | grep -q "$container_name"; then
    log_info "Stopping and removing $container_name container"
    docker stop "$container_name" &> /dev/null || true
    docker rm "$container_name" &> /dev/null || true
  fi
}

wait_for_health() {
  local container_name=$1
  local health_url=$2
  local timeout=$3

  log_info "Waiting for $container_name to be healthy (timeout: ${timeout}s)"

  local start_time=$(date +%s)
  local end_time=$((start_time + timeout))

  while [ $(date +%s) -lt $end_time ]; do
    if curl -s -o /dev/null -w "%{http_code}" "$health_url" | grep -q "200"; then
      log_success "$container_name is healthy"
      return 0
    fi

    # Check if container is still running
    if ! docker ps --format "{{.Names}}" | grep -q "$container_name"; then
      log_error "$container_name container stopped unexpectedly"
      docker logs "$container_name" | tail -n 50
      return 1
    fi

    echo -n "."
    sleep 1
  done

  log_error "$container_name health check timed out after ${timeout}s"
  return 1
}

# =============================================================================
# Parse command line arguments
# =============================================================================

while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help)
      show_help
      exit 0
      ;;
    -b|--backend-port)
      BACKEND_PORT="$2"
      shift 2
      ;;
    -f|--frontend-port)
      FRONTEND_PORT="$2"
      shift 2
      ;;
    --backend-image)
      BACKEND_IMAGE="$2"
      shift 2
      ;;
    --frontend-image)
      FRONTEND_IMAGE="$2"
      shift 2
      ;;
    -e|--env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    -n|--network)
      NETWORK_NAME="$2"
      shift 2
      ;;
    --timeout)
      HEALTH_CHECK_TIMEOUT="$2"
      shift 2
      ;;
    *)
      log_error "Unknown option: $1"
      show_help
      exit 1
      ;;
  esac
done

# =============================================================================
# Main execution
# =============================================================================

log_info "Starting Langflow stack with:"
log_info "  Backend Image: $BACKEND_IMAGE (Port: $BACKEND_PORT)"
log_info "  Frontend Image: $FRONTEND_IMAGE (Port: $FRONTEND_PORT)"
log_info "  Network: $NETWORK_NAME"
log_info "  Environment file: $ENV_FILE"

# Validate environment file
if [ ! -f "$ENV_FILE" ] && [ ! -f "$ROOT_DIR/$ENV_FILE" ]; then
  log_warning "Environment file not found: $ENV_FILE"
  read -p "Continue without environment file? [y/N] " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_error "Aborted by user"
    exit 1
  fi
  ENV_FILE=""
fi

# Create network if it doesn't exist
if ! docker network inspect "$NETWORK_NAME" > /dev/null 2>&1; then
  log_info "Creating network $NETWORK_NAME"
  docker network create "$NETWORK_NAME"
  log_success "Network created"
fi

# Setup and run backend container
log_info "Setting up backend container"
cleanup_container "$BACKEND_CONTAINER_NAME"

# Prepare environment file mount
ENV_MOUNT=""
ENV_ARG=""
if [ -n "$ENV_FILE" ]; then
  if [ -f "$ENV_FILE" ]; then
    ENV_MOUNT="--mount type=bind,source=$(realpath "$ENV_FILE"),target=/app/.env"
    ENV_ARG="--env-file /app/.env"
  elif [ -f "$ROOT_DIR/$ENV_FILE" ]; then
    ENV_MOUNT="--mount type=bind,source=$(realpath "$ROOT_DIR/$ENV_FILE"),target=/app/.env"
    ENV_ARG="--env-file /app/.env"
  fi
fi

# Run backend container
log_info "Starting backend container"
docker run -d \
  --name "$BACKEND_CONTAINER_NAME" \
  --network "$NETWORK_NAME" \
  -p "${BACKEND_PORT}:${BACKEND_PORT}" \
  -p 9090:9090 \
  --sysctl net.ipv6.conf.all.disable_ipv6=1 \
  $ENV_MOUNT \
  "$BACKEND_IMAGE" $ENV_ARG

# Wait for backend to be healthy
wait_for_health "$BACKEND_CONTAINER_NAME" "http://localhost:${BACKEND_PORT}/health" "$HEALTH_CHECK_TIMEOUT" || {
  log_error "Backend failed to start properly. See logs above."
  exit 1
}

# Setup and run frontend container
log_info "Setting up frontend container"
cleanup_container "$FRONTEND_CONTAINER_NAME"

# Run frontend container
log_info "Starting frontend container"
docker run -d \
  --name "$FRONTEND_CONTAINER_NAME" \
  --network "$NETWORK_NAME" \
  -p "${FRONTEND_PORT}:${FRONTEND_PORT}" \
  -e "BACKEND_URL=http://${BACKEND_CONTAINER_NAME}:${BACKEND_PORT}" \
  -e "SUPPRESS_PROBE_LOGS=true" \
  -e "DEBUG=true" \
  --sysctl net.ipv6.conf.all.disable_ipv6=1 \
  "$FRONTEND_IMAGE"

# Wait for frontend to be healthy
wait_for_health "$FRONTEND_CONTAINER_NAME" "http://localhost:${FRONTEND_PORT}/nginx_health" "$HEALTH_CHECK_TIMEOUT" || {
  log_error "Frontend failed to start properly. See logs above."
  exit 1
}

# =============================================================================
# Success message
# =============================================================================

log_success "Langflow is running successfully!"
log_success "Frontend: http://localhost:${FRONTEND_PORT}"
log_success "Backend API: http://localhost:${BACKEND_PORT}"
log_success "Backend Health: http://localhost:${BACKEND_PORT}/health"

# Always show the manual cleanup commands
log_info "To manually stop and remove the containers when done:"
log_info "  docker stop $FRONTEND_CONTAINER_NAME $BACKEND_CONTAINER_NAME"
log_info "  docker rm $FRONTEND_CONTAINER_NAME $BACKEND_CONTAINER_NAME"

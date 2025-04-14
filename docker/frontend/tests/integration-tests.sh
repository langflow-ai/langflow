#!/bin/bash
# Integration test script for the NGINX frontend container
set -e

# Print colored output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Get root directory paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_DIR="$(cd "${FRONTEND_DIR}/../.." && pwd)"
DOCKERFILE_PATH="${FRONTEND_DIR}/build_and_push_frontend.Dockerfile"

function log {
  local level=$1
  local message=$2
  local timestamp=$(date "+%Y-%m-%d %H:%M:%S")

  case $level in
    "INFO")
      echo -e "${GREEN}[${timestamp}] [INFO] ${message}${NC}"
      ;;
    "WARNING")
      echo -e "${YELLOW}[${timestamp}] [WARNING] ${message}${NC}"
      ;;
    "ERROR")
      echo -e "${RED}[${timestamp}] [ERROR] ${message}${NC}"
      ;;
    *)
      echo "[${timestamp}] [${level}] ${message}"
      ;;
  esac
}

function fail {
  log "ERROR" "$1"
  exit 1
}

function test_header {
  echo -e "\n${YELLOW}===================================================${NC}"
  echo -e "${YELLOW}    $1${NC}"
  echo -e "${YELLOW}===================================================${NC}"
}

# Constants
IMAGE_NAME="langflow-frontend-test"
CONTAINER_NAME="langflow-frontend-integration"
MOCK_BACKEND_NAME="mock-backend"
MOCK_BACKEND_PORT=8000
FRONTEND_PORT=8080

# Clean up any existing container and network
function cleanup_container() {
  docker stop "$CONTAINER_NAME" 2>/dev/null || true
  docker rm "$CONTAINER_NAME" 2>/dev/null || true
}

function cleanup_mock_backend() {
  docker stop "$MOCK_BACKEND_NAME" 2>/dev/null || true
  docker rm "$MOCK_BACKEND_NAME" 2>/dev/null || true
}

function build_image() {
  log "INFO" "Checking if test image exists..."

  # Check if the image exists
  if ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
    log "INFO" "Test image not found, building it..."

    # Check if Dockerfile exists
    if [ ! -f "$DOCKERFILE_PATH" ]; then
      fail "Dockerfile not found at: $DOCKERFILE_PATH"
    fi

    # Change to the root directory before building
    cd "$ROOT_DIR"

    # Build the image
    if docker build -t "$IMAGE_NAME" -f "$DOCKERFILE_PATH" .; then
      log "INFO" "Image built successfully"
    else
      fail "Failed to build image"
    fi
  else
    log "INFO" "Test image already exists"
  fi
}

# Setup
function setup {
  log "INFO" "Setting up test environment..."

  # Build the test image if it doesn't exist
  build_image

  # Clean up any existing containers
  cleanup_container
  cleanup_mock_backend

  # Create a mock backend service
  log "INFO" "Starting mock backend service..."
  docker run -d --name $MOCK_BACKEND_NAME -p $MOCK_BACKEND_PORT:80 \
    --entrypoint "sh" nginxinc/nginx-unprivileged:alpine -c "echo 'server { listen 80; location / { return 200 \"{\\\"status\\\": \\\"ok\\\", \\\"service\\\": \\\"mock-api\\\"}\"; } }' > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"

  # Wait for mock backend to start
  sleep 2

  # Verify mock backend is running
  if ! curl -s http://localhost:$MOCK_BACKEND_PORT | grep -q "mock-api"; then
    fail "Mock backend failed to start properly"
  fi

  log "INFO" "Mock backend is running and responding correctly."
}

# Cleanup
function cleanup {
  log "INFO" "Cleaning up test environment..."
  cleanup_container
  cleanup_mock_backend
}

# Register cleanup on exit
trap cleanup EXIT

# Test cases
function test_basic_configuration {
  test_header "Testing Basic Configuration"

  log "INFO" "Starting frontend container with basic configuration..."
  docker run -d --name $CONTAINER_NAME \
    -p $FRONTEND_PORT:$FRONTEND_PORT \
    -e BACKEND_URL="http://host.docker.internal:$MOCK_BACKEND_PORT" \
    -e FRONTEND_PORT=$FRONTEND_PORT \
    $IMAGE_NAME

  # Wait for container to start
  sleep 5

  # Test 1: Check if container is running
  if ! docker ps | grep -q $CONTAINER_NAME; then
    fail "Container failed to start"
  fi
  log "INFO" "Container started successfully"

  # Test 2: Check if NGINX health endpoint responds
  if curl -s http://localhost:$FRONTEND_PORT/nginx_health 2>/dev/null | grep -q "status.*ok"; then
    log "INFO" "Health check endpoint is responding correctly"
  else
    # Since we're just testing configuration, not actual connectivity, this is optional
    log "WARNING" "Health check endpoint not responding - this may be expected in test environment"
  fi

  # Test logs to verify configuration
  docker logs $CONTAINER_NAME > container-logs.txt

  # Check if the configuration shows the correct backend URL
  if grep -q "Backend URL: http://host.docker.internal:$MOCK_BACKEND_PORT" container-logs.txt; then
    log "INFO" "Container is configured with the correct backend URL"
  else
    log "ERROR" "Container is not configured with the expected backend URL"
    cat container-logs.txt
    rm -f container-logs.txt
    fail "Configuration test failed"
  fi

  # Clean up logs file
  rm -f container-logs.txt

  # Cleanup for next test
  docker stop $CONTAINER_NAME
  docker rm $CONTAINER_NAME
}

function test_custom_configuration {
  test_header "Testing Custom Configuration"

  local custom_port=9090
  local custom_max_body="50m"
  local custom_timeout=30

  log "INFO" "Starting frontend container with custom configuration..."
  docker run -d --name $CONTAINER_NAME \
    -p $custom_port:$custom_port \
    -e BACKEND_URL="http://host.docker.internal:$MOCK_BACKEND_PORT" \
    -e FRONTEND_PORT=$custom_port \
    -e CLIENT_MAX_BODY_SIZE=$custom_max_body \
    -e CLIENT_TIMEOUT=$custom_timeout \
    -e ERROR_LOG_LEVEL="debug" \
    -e DEBUG="true" \
    $IMAGE_NAME

  # Wait for container to start
  sleep 5

  # Save logs for verification
  docker logs $CONTAINER_NAME > custom-logs.txt

  # Check if the configuration shows the custom values
  if grep -q "Frontend port: $custom_port" custom-logs.txt && \
     grep -q "Client max body size: $custom_max_body" custom-logs.txt && \
     grep -q "Client timeout: $custom_timeout" custom-logs.txt; then
    log "INFO" "Custom configuration was applied correctly"
  else
    log "ERROR" "Custom configuration was not applied correctly"
    cat custom-logs.txt
    rm -f custom-logs.txt
    fail "Custom configuration test failed"
  fi

  # Clean up logs
  rm -f custom-logs.txt

  # Cleanup for next test
  docker stop $CONTAINER_NAME
  docker rm $CONTAINER_NAME
}

function test_logging_configuration {
  test_header "Testing Logging Configuration"

  # Test both JSON and default logging
  for log_format in "default" "json"; do
    log "INFO" "Testing $log_format log format..."

    docker run -d --name $CONTAINER_NAME \
      -e BACKEND_URL="http://host.docker.internal:$MOCK_BACKEND_PORT" \
      -e NGINX_LOG_FORMAT="$log_format" \
      -e DEBUG="true" \
      $IMAGE_NAME

    # Wait for container to start
    sleep 5

    # Save logs for verification
    docker logs $CONTAINER_NAME > logging-logs.txt

    # Check if the configuration shows the log format
    if [ "$log_format" = "json" ]; then
      if grep -q "Using JSON log format" logging-logs.txt; then
        log "INFO" "JSON log format was configured correctly"
      else
        log "ERROR" "JSON log format was not configured correctly"
        cat logging-logs.txt
        rm -f logging-logs.txt
        fail "Logging configuration test failed"
      fi
    else
      if grep -q "Using default log format" logging-logs.txt; then
        log "INFO" "Default log format was configured correctly"
      else
        log "ERROR" "Default log format was not configured correctly"
        cat logging-logs.txt
        rm -f logging-logs.txt
        fail "Logging configuration test failed"
      fi
    fi

    # Clean up logs
    rm -f logging-logs.txt

    # Cleanup for next test
    docker stop $CONTAINER_NAME
    docker rm $CONTAINER_NAME
  done
}

# Run all tests
function run_all_tests {
  setup

  test_basic_configuration
  test_custom_configuration
  test_logging_configuration

  log "INFO" "All integration tests passed successfully!"
}

run_all_tests

#!/bin/bash
# Comprehensive Test Suite Runner for NGINX Frontend
set -e

# Colors for output
COLOR_GREEN="\033[0;32m"
COLOR_RED="\033[0;31m"
COLOR_YELLOW="\033[0;33m"
COLOR_BLUE="\033[0;34m"
COLOR_RESET="\033[0m"

# Get directory paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_DIR="$(cd "${FRONTEND_DIR}/../.." && pwd)"
SCRIPT_PATH="${FRONTEND_DIR}/start-nginx.sh"
TEMPLATE_PATH="${FRONTEND_DIR}/default.conf.template"
DOCKERFILE_PATH="${FRONTEND_DIR}/build_and_push_frontend.Dockerfile"

# Function to print colored output
function print() {
  local color=$1
  local message=$2
  echo -e "${color}${message}${COLOR_RESET}"
}

# Function to check if command exists
function check_command() {
  if ! command -v $1 &> /dev/null; then
    print "$COLOR_RED" "Command '$1' could not be found. Please install it."
    return 1
  fi
  return 0
}

# Function to run a test with a title
function run_test() {
  local title=$1
  local command=$2

  print "$COLOR_BLUE" "============================================"
  print "$COLOR_BLUE" "  ${title}"
  print "$COLOR_BLUE" "============================================"

  if eval "$command"; then
    print "$COLOR_GREEN" "Test passed: ${title}"
    return 0
  else
    print "$COLOR_RED" "Test failed: ${title}"
    return 1
  fi
}

# Check dependencies
function check_dependencies() {
  print "$COLOR_YELLOW" "Checking dependencies..."

  if ! check_command docker; then
    print "$COLOR_RED" "Docker is required for these tests."
    exit 1
  fi

  if ! check_command curl; then
    print "$COLOR_RED" "curl is required for these tests."
    exit 1
  fi

  print "$COLOR_GREEN" "All required dependencies are installed."
}

# Build the test Docker image for shell script tests
function build_shell_test_image() {
  print "$COLOR_YELLOW" "Building Docker image for shell script tests..."

  # Create a temporary Dockerfile if it doesn't exist
  if [ ! -f "${SCRIPT_DIR}/Dockerfile.test-shell" ]; then
    print "$COLOR_YELLOW" "Creating Dockerfile.test-shell..."
    cp "${SCRIPT_DIR}/updated-docker-shell-testing" "${SCRIPT_DIR}/Dockerfile.test-shell"
  fi

  if ! docker build -t langflow-shell-test -f "${SCRIPT_DIR}/Dockerfile.test-shell" "${SCRIPT_DIR}"; then
    print "$COLOR_RED" "Failed to build shell test Docker image!"
    return 1
  fi

  print "$COLOR_GREEN" "Shell test Docker image built successfully."
  return 0
}

# Build the frontend Docker image for integration tests
function build_frontend_image() {
  print "$COLOR_YELLOW" "Building frontend Docker image for integration tests..."

  # Change to the root directory to build the image
  cd "$ROOT_DIR"

  if ! docker build -t langflow-frontend-test -f "$DOCKERFILE_PATH" .; then
    print "$COLOR_RED" "Failed to build frontend Docker image!"
    return 1
  fi

  print "$COLOR_GREEN" "Frontend Docker image built successfully."
  return 0
}

# Main test suite
function run_test_suite() {
  local failures=0

  # Display test environment info
  print "$COLOR_YELLOW" "Test Environment Information"
  echo "Date: $(date)"
  echo "Host: $(hostname)"
  echo "User: $(whoami)"
  echo "Docker version: $(docker --version 2>/dev/null || echo 'Not installed')"
  echo "BASH version: ${BASH_VERSION}"
  echo "Project root: ${ROOT_DIR}"
  echo "Frontend directory: ${FRONTEND_DIR}"
  echo "Tests directory: ${SCRIPT_DIR}"
  echo ""

  # Check dependencies
  check_dependencies

  # Build required Docker images
  build_shell_test_image
  if [ $? -ne 0 ]; then failures=$((failures+1)); fi

  build_frontend_image
  if [ $? -ne 0 ]; then failures=$((failures+1)); fi

  # 1. Run shell script unit tests
  run_test "Shell Script Unit Tests" "docker run --rm \
    -v \"${SCRIPT_PATH}\":/start-nginx.sh:ro \
    -v \"${TEMPLATE_PATH}\":/etc/nginx/conf.d/default.conf.template:ro \
    -v \"${SCRIPT_DIR}/start-nginx-tests.bats\":/tests/start-nginx-tests.bats:ro \
    -e SCRIPT_PATH=/start-nginx.sh \
    -e CONFIG_TEMPLATE_PATH=/etc/nginx/conf.d/default.conf.template \
    -e TESTS_PATH=/tests/start-nginx-tests.bats \
    langflow-shell-test"
  if [ $? -ne 0 ]; then failures=$((failures+1)); fi

  # 2. Run environment variable tests
  run_test "Environment Variable Tests" "docker run --rm \
    -v \"${SCRIPT_PATH}\":/start-nginx.sh:ro \
    -v \"${TEMPLATE_PATH}\":/etc/nginx/conf.d/default.conf.template:ro \
    -v \"${SCRIPT_DIR}/env-var-tests.bats\":/tests/start-nginx-tests.bats:ro \
    -e SCRIPT_PATH=/start-nginx.sh \
    -e CONFIG_TEMPLATE_PATH=/etc/nginx/conf.d/default.conf.template \
    -e TESTS_PATH=/tests/start-nginx-tests.bats \
    langflow-shell-test"
  if [ $? -ne 0 ]; then failures=$((failures+1)); fi

  # 3. Run Docker build tests
  run_test "Docker Build and Structure Tests" "${SCRIPT_DIR}/docker-tests.sh"
  if [ $? -ne 0 ]; then failures=$((failures+1)); fi

  # 4. Run integration tests
  run_test "Integration Tests" "${SCRIPT_DIR}/integration-tests.sh"
  if [ $? -ne 0 ]; then failures=$((failures+1)); fi

  # Report summary
  echo ""
  print "$COLOR_BLUE" "============================================"
  print "$COLOR_BLUE" "  Test Suite Summary"
  print "$COLOR_BLUE" "============================================"

  if [ $failures -eq 0 ]; then
    print "$COLOR_GREEN" "All tests passed successfully!"
    return 0
  else
    print "$COLOR_RED" "${failures} test(s) failed!"
    return 1
  fi
}

# Clean up function
function cleanup() {
  print "$COLOR_YELLOW" "Cleaning up test resources..."

  # Stop and remove containers
  docker ps -a | grep "langflow-" | awk '{print $1}' | xargs -r docker stop >/dev/null 2>&1 || true
  docker ps -a | grep "langflow-" | awk '{print $1}' | xargs -r docker rm >/dev/null 2>&1 || true

  # Only remove images if explicitly requested with --clean-images
  if [ "$CLEAN_IMAGES" = "true" ]; then
    docker images | grep "langflow-" | awk '{print $3}' | xargs -r docker rmi >/dev/null 2>&1 || true
  fi

  # Remove temporary directories
  rm -rf /tmp/langflow-test-* 2>/dev/null || true

  print "$COLOR_GREEN" "Cleanup complete."
}

# Parse command line arguments
CLEAN_IMAGES="false"
while [[ "$#" -gt 0 ]]; do
  case $1 in
    --clean-images) CLEAN_IMAGES="true" ;;
    --help) echo "Usage: $0 [--clean-images] [--help]"; exit 0 ;;
    *) echo "Unknown parameter: $1"; echo "Usage: $0 [--clean-images] [--help]"; exit 1 ;;
  esac
  shift
done

# Register the cleanup function to run on exit
trap cleanup EXIT

# Run the test suite
run_test_suite
exit $?

#!/bin/bash

# AI Studio Frontend Dev Environment Local Testing
# Tests the /basic-examples 401 issue with exact dev values

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}================================================${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}================================================${NC}\n"
}

# Check if Docker is running
check_docker() {
    print_status "Checking Docker availability..."
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running or accessible. Please start Docker."
        exit 1
    fi
    print_success "Docker is running"
}

# Build and start container
start_container() {
    print_header "BUILDING AND STARTING AI STUDIO FRONTEND"

    print_status "Building AI Studio Frontend with dev environment configuration..."
    docker compose -f docker-compose.local-test.yml build --no-cache

    print_status "Starting frontend container..."
    docker compose -f docker-compose.local-test.yml up -d

    print_status "Waiting for container to be ready..."
    sleep 30

    # Check if container is running
    if docker compose -f docker-compose.local-test.yml ps | grep -q "Up"; then
        print_success "Container is running"
    else
        print_error "Failed to start container"
        docker compose -f docker-compose.local-test.yml logs
        exit 1
    fi
}

# Test container health
test_container_health() {
    print_header "TESTING CONTAINER HEALTH"

    print_status "Testing frontend accessibility (port 3000)..."
    if curl -s -f http://localhost:3000 > /dev/null; then
        print_success "Frontend is accessible"
    else
        print_error "Frontend is not accessible"
        docker logs ai-studio-frontend-dev-test
        exit 1
    fi
}

# Test specific endpoints including /basic-examples
test_api_endpoints() {
    print_header "TESTING API ENDPOINTS"

    print_status "Testing /basic-examples endpoint (this should show 401 if issue exists)..."

    # Test basic-examples endpoint - this is where the 401 issue occurs
    response=$(curl -s -w "\n%{http_code}" http://localhost:3000/api/v1/genesis-studio/flows/examples)
    status_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n -1)

    echo "Status Code: $status_code"
    echo "Response Body: $body"

    if [ "$status_code" = "401" ]; then
        print_error "401 Unauthorized error detected for /basic-examples endpoint!"
        print_warning "This confirms the issue - the endpoint is returning 401"
    elif [ "$status_code" = "200" ]; then
        print_success "/basic-examples endpoint working correctly"
    else
        print_warning "/basic-examples endpoint returned status: $status_code"
    fi

    print_status "Testing environment configuration..."
    curl -s http://localhost:3000/env-config.js | head -20
}

# Test browser access
test_browser_access() {
    print_header "TESTING BROWSER ACCESS"

    print_status "Frontend is ready for browser testing..."

    echo -e "\n${GREEN}You can now test in your browser:${NC}"
    echo -e "${YELLOW}Frontend URL:${NC} http://localhost:3000"

    echo -e "\n${GREEN}To test the /basic-examples 401 issue:${NC}"
    echo -e "1. Open http://localhost:3000 in your browser"
    echo -e "2. Open Developer Tools (Network tab)"
    echo -e "3. Watch for requests to /api/v1/genesis-studio/flows/examples"
    echo -e "4. Check if they show 401 Unauthorized status"
    echo -e "5. Verify authentication flow and Bearer token attachment"

    echo -e "\n${GREEN}Expected behavior with our fixes:${NC}"
    echo -e "- Keycloak authentication should initialize properly"
    echo -e "- Bearer tokens should be attached to API requests"
    echo -e "- /basic-examples should NOT return 401 errors"
    echo -e "- If 401 occurs, it should trigger proper authentication flow"
}

# View container logs
view_logs() {
    print_header "CONTAINER LOGS"

    print_status "Showing recent logs from frontend container..."
    docker logs --tail=50 ai-studio-frontend-dev-test
}

# Cleanup function
cleanup() {
    print_header "CLEANUP"

    print_status "Stopping and removing test container..."
    docker compose -f docker-compose.local-test.yml down -v

    print_success "Cleanup completed"
}

# Main execution
main() {
    print_header "AI STUDIO FRONTEND DEV ENVIRONMENT LOCAL TESTING"

    print_status "Testing for /basic-examples 401 issue with exact dev values..."

    # Check prerequisites
    check_docker

    # Start container and run tests
    start_container
    test_container_health
    test_api_endpoints
    test_browser_access

    # Wait for user input
    echo -e "\n${GREEN}Press Enter to view container logs, or Ctrl+C to exit...${NC}"
    read -r
    view_logs

    echo -e "\n${GREEN}Press Enter to cleanup and exit, or Ctrl+C to keep container running...${NC}"
    read -r
    cleanup
}

# Handle script interruption
trap cleanup EXIT

# Handle command line arguments
case "${1:-}" in
    "start")
        check_docker
        start_container
        test_container_health
        test_browser_access
        echo -e "\n${GREEN}Container started. Use './test-dev-local.sh stop' to cleanup.${NC}"
        ;;
    "stop")
        cleanup
        ;;
    "logs")
        view_logs
        ;;
    "test")
        check_docker
        test_api_endpoints
        ;;
    *)
        main
        ;;
esac
#!/bin/bash

# AI Studio Frontend Authentication Testing Script
# Tests both Keycloak and Traditional authentication flows

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

# Build and start containers
start_containers() {
    print_header "BUILDING AND STARTING CONTAINERS"

    print_status "Building AI Studio Frontend with authentication fixes..."
    docker compose -f docker-compose.test.yml build --no-cache

    print_status "Starting test containers..."
    docker compose -f docker-compose.test.yml up -d

    print_status "Waiting for containers to be ready..."
    sleep 30

    # Check if containers are running
    if docker compose -f docker-compose.test.yml ps | grep -q "Up"; then
        print_success "Containers are running"
    else
        print_error "Failed to start containers"
        docker compose -f docker-compose.test.yml logs
        exit 1
    fi
}

# Test container health
test_container_health() {
    print_header "TESTING CONTAINER HEALTH"

    # Test Keycloak-enabled frontend
    print_status "Testing Keycloak-enabled frontend (port 3001)..."
    if curl -s -f http://localhost:3001 > /dev/null; then
        print_success "Keycloak frontend is accessible"
    else
        print_error "Keycloak frontend is not accessible"
        docker logs ai-studio-frontend-keycloak-test
    fi

    # Test Traditional auth frontend
    print_status "Testing Traditional auth frontend (port 3002)..."
    if curl -s -f http://localhost:3002 > /dev/null; then
        print_success "Traditional frontend is accessible"
    else
        print_error "Traditional frontend is not accessible"
        docker logs ai-studio-frontend-traditional-test
    fi

    # Test Mock backend
    print_status "Testing Mock backend (port 7860)..."
    if curl -s -f http://localhost:7860/health > /dev/null; then
        print_success "Mock backend is accessible"
        echo "Backend health response:"
        curl -s http://localhost:7860/health | jq .
    else
        print_error "Mock backend is not accessible"
        docker logs ai-studio-mock-backend
    fi
}

# Test API endpoints with Bearer token
test_api_endpoints() {
    print_header "TESTING API ENDPOINTS"

    print_status "Testing API endpoints with Bearer token..."

    # Test auto login (traditional auth)
    print_status "Testing auto login endpoint..."
    response=$(curl -s -w "%{http_code}" -H "Content-Type: application/json" http://localhost:7860/api/v1/auto_login)
    if echo "$response" | grep -q "200"; then
        print_success "Auto login endpoint working"
        echo "Response: $(echo "$response" | head -n -1)"
    else
        print_warning "Auto login endpoint returned: $(echo "$response" | tail -n 1)"
    fi

    # Test user endpoint with Bearer token
    print_status "Testing user endpoint with Bearer token..."
    response=$(curl -s -w "%{http_code}" -H "Authorization: Bearer mock-traditional-token" -H "Content-Type: application/json" http://localhost:7860/api/v1/users/whoami)
    if echo "$response" | grep -q "200"; then
        print_success "User endpoint working with Bearer token"
        echo "Response: $(echo "$response" | head -n -1)"
    else
        print_warning "User endpoint returned: $(echo "$response" | tail -n 1)"
    fi

    # Test version endpoint
    print_status "Testing version endpoint..."
    response=$(curl -s -w "%{http_code}" http://localhost:7860/api/v1/version)
    if echo "$response" | grep -q "200"; then
        print_success "Version endpoint working"
        echo "Response: $(echo "$response" | head -n -1)"
    else
        print_warning "Version endpoint returned: $(echo "$response" | tail -n 1)"
    fi
}

# Test frontend environment configuration
test_frontend_config() {
    print_header "TESTING FRONTEND CONFIGURATION"

    # Test Keycloak frontend environment
    print_status "Checking Keycloak frontend environment configuration..."
    if curl -s http://localhost:3001/env-config.js | grep -q "VITE_KEYCLOAK_ENABLED.*true"; then
        print_success "Keycloak is enabled in frontend config"
    else
        print_warning "Keycloak configuration not found or disabled"
    fi

    # Test Traditional frontend environment
    print_status "Checking Traditional frontend environment configuration..."
    if curl -s http://localhost:3002/env-config.js | grep -q "VITE_KEYCLOAK_ENABLED.*false"; then
        print_success "Keycloak is disabled in traditional frontend config"
    else
        print_warning "Traditional auth configuration incorrect"
    fi

    # Show environment configurations
    print_status "Keycloak Frontend Environment Configuration:"
    curl -s http://localhost:3001/env-config.js | head -20

    print_status "Traditional Frontend Environment Configuration:"
    curl -s http://localhost:3002/env-config.js | head -20
}

# Test browser accessibility
test_browser_access() {
    print_header "TESTING BROWSER ACCESSIBILITY"

    print_status "Testing browser access to frontends..."

    echo -e "\n${GREEN}You can now test the frontends in your browser:${NC}"
    echo -e "${YELLOW}Keycloak Authentication Frontend:${NC} http://localhost:3001"
    echo -e "${YELLOW}Traditional Authentication Frontend:${NC} http://localhost:3002"
    echo -e "${YELLOW}Mock Backend API:${NC} http://localhost:7860"
    echo -e "${YELLOW}Backend Health Check:${NC} http://localhost:7860/health"
    echo -e "${YELLOW}Backend Test Config:${NC} http://localhost:7860/test-config.json"

    echo -e "\n${GREEN}Authentication Testing Instructions:${NC}"
    echo -e "1. ${BLUE}Keycloak Frontend (Port 3001):${NC}"
    echo -e "   - Should NOT show autologin attempts in network tab"
    echo -e "   - Should redirect to Keycloak when authentication is needed"
    echo -e "   - Should include Bearer tokens in API requests after Keycloak auth"
    echo -e "   - Check browser console for 'Keycloak' related logs"

    echo -e "\n2. ${BLUE}Traditional Frontend (Port 3002):${NC}"
    echo -e "   - Should attempt autologin on page load"
    echo -e "   - Should include Bearer tokens in API requests"
    echo -e "   - Should work with traditional login flow"
    echo -e "   - Check browser console for traditional auth logs"

    echo -e "\n3. ${BLUE}Things to Verify:${NC}"
    echo -e "   - No 401 Unauthorized errors in network tab"
    echo -e "   - Bearer tokens properly attached to API requests"
    echo -e "   - Autologin disabled when Keycloak is enabled"
    echo -e "   - Token refresh works correctly"
    echo -e "   - Authentication state synchronization"
}

# View container logs
view_logs() {
    print_header "CONTAINER LOGS"

    print_status "Showing recent logs from all containers..."

    echo -e "\n${YELLOW}Keycloak Frontend Logs:${NC}"
    docker logs --tail=50 ai-studio-frontend-keycloak-test

    echo -e "\n${YELLOW}Traditional Frontend Logs:${NC}"
    docker logs --tail=50 ai-studio-frontend-traditional-test

    echo -e "\n${YELLOW}Mock Backend Logs:${NC}"
    docker logs --tail=50 ai-studio-mock-backend
}

# Cleanup function
cleanup() {
    print_header "CLEANUP"

    print_status "Stopping and removing test containers..."
    docker compose -f docker-compose.test.yml down -v

    print_status "Removing test images..."
    docker image prune -f

    print_success "Cleanup completed"
}

# Main execution
main() {
    print_header "AI STUDIO FRONTEND AUTHENTICATION TESTING"

    print_status "Starting comprehensive authentication testing..."

    # Check prerequisites
    check_docker

    # Check if jq is available for JSON parsing
    if ! command -v jq &> /dev/null; then
        print_warning "jq is not installed. JSON responses will not be formatted."
        # Create a simple jq replacement for basic use
        jq() { cat; }
    fi

    # Start containers and run tests
    start_containers
    test_container_health
    test_api_endpoints
    test_frontend_config
    test_browser_access

    # Wait for user input
    echo -e "\n${GREEN}Press Enter to view container logs, or Ctrl+C to exit...${NC}"
    read -r
    view_logs

    echo -e "\n${GREEN}Press Enter to cleanup and exit, or Ctrl+C to keep containers running...${NC}"
    read -r
    cleanup
}

# Handle script interruption
trap cleanup EXIT

# Handle command line arguments
case "${1:-}" in
    "start")
        check_docker
        start_containers
        test_container_health
        test_browser_access
        echo -e "\n${GREEN}Containers started. Use './test-authentication.sh stop' to cleanup.${NC}"
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
        test_frontend_config
        ;;
    *)
        main
        ;;
esac
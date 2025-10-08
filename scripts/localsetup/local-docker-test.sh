#!/bin/bash

# Simple script for local Docker testing with Postgres
# Usage: ./local-docker-test.sh [build|run|stop]

set -e

# Change to git root directory
echo "📂 Changing to git root directory..."
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$GIT_ROOT" ]; then
    echo "❌ Error: Not in a git repository!"
    echo "This script must be run from within a git repository."
    exit 1
fi

cd "$GIT_ROOT"
echo "✅ Now in: $(pwd)"
echo ""

# Function to display help
show_help() {
    cat << 'EOF'
🐳 Local Docker Testing Script

📋 Usage:
    ./local-docker-test.sh [COMMAND] [OPTIONS]

🔧 Commands:
    build              Build the Docker image with staging environment variables
    run [IMAGE_TAG]    Run Docker containers (Langflow + Postgres)
                      - If IMAGE_TAG is provided, uses that specific image
                      - If omitted, shows interactive menu to select from available images
    stop              Stop and remove Docker containers
    -h, --help        Show this help message

📖 Description:
    This script helps you test the Langflow Docker container locally with Postgres.
    
    🔨 Build: Creates the Docker image using staging environment variables
              matching the GitHub workflow configuration.
    
    ▶️  Run:   Starts two containers:
              - Postgres database (port 5432)
              - Langflow application (port 7860)
              Interactive menu allows you to select from available images.
              Uses .env-file for runtime configuration.
    
    🛑 Stop:  Stops and removes all containers and networks.

⚙️  Prerequisites:
    1. Docker must be installed and running
    2. .env-file must exist in the project root
    3. VITE_CLERK_PUBLISHABLE_KEY environment variable must be set

🔑 Required Environment Variable:
    VITE_CLERK_PUBLISHABLE_KEY - Clerk publishable key (required for build)
    
    To set it, run:
    export VITE_CLERK_PUBLISHABLE_KEY="pk_test_your_key_here"

💡 Examples:
    # Set the required environment variable
    export VITE_CLERK_PUBLISHABLE_KEY="pk_test_xxxxxxxxxxxx"
    
    # Build the Docker image
    ./local-docker-test.sh build
    
    # Run the containers with a specific image
    ./local-docker-test.sh run langflow:localbuild_20241008_120000
    
    # Run the containers (will prompt for image selection)
    ./local-docker-test.sh run
    
    # Stop the containers
    ./local-docker-test.sh stop

🌐 Access:
    Langflow UI:  http://localhost:7860
    Postgres DB:  localhost:5432 (user: langflow, password: langflow, db: langflow)

🔍 Troubleshooting:
    View container logs:
        docker logs langflow-local-test
        docker logs langflow-postgres-local
    
    Check running containers:
        docker ps

EOF
}

# Check if VITE_CLERK_PUBLISHABLE_KEY is set
check_clerk_key() {
    if [ -z "${VITE_CLERK_PUBLISHABLE_KEY:-}" ]; then
        echo "❌ Error: VITE_CLERK_PUBLISHABLE_KEY environment variable is not set!"
        echo ""
        echo "🔑 This is a required environment variable for building the Docker image."
        echo ""
        echo "✅ To set it, run:"
        echo "    export VITE_CLERK_PUBLISHABLE_KEY=\"pk_test_your_key_here\""
        echo ""
        echo "📝 Then run the build command again:"
        echo "    $0 build"
        echo ""
        exit 1
    fi
    echo "✅ VITE_CLERK_PUBLISHABLE_KEY is set"
}

# Configuration from GitHub workflow (staging environment)
VITE_AUTO_LOGIN=false
VITE_CLERK_AUTH_ENABLED=true
VITE_CLERK_PUBLISHABLE_KEY="${VITE_CLERK_PUBLISHABLE_KEY:-}"

# Docker image details
IMAGE_NAME="langflow"
IMAGE_TAG="localbuild_$(date +%Y%m%d_%H%M%S)"
CONTAINER_NAME="langflow-local-test"
POSTGRES_CONTAINER="langflow-postgres-local"
NETWORK_NAME="langflow-test-network"

# Postgres configuration
POSTGRES_DB="langflow"
POSTGRES_USER="langflow"
POSTGRES_PASSWORD="langflow"
POSTGRES_PORT="5432"

# Function to build Docker image
build_docker() {
    # Check for required environment variable
    check_clerk_key
    
    echo "🔨 Building Docker image..."
    
    TAG="${IMAGE_NAME}:${IMAGE_TAG}" \
    DOCKER_BUILDKIT=1 \
    VITE_AUTO_LOGIN=${VITE_AUTO_LOGIN} \
    VITE_CLERK_AUTH_ENABLED=${VITE_CLERK_AUTH_ENABLED} \
    VITE_CLERK_PUBLISHABLE_KEY=${VITE_CLERK_PUBLISHABLE_KEY} \
    make docker_build
    
    echo "✅ Docker image built successfully"
    echo "📦 Image tag: ${IMAGE_NAME}:${IMAGE_TAG}"
    echo ""
    echo "💡 To run this image, use:"
    echo "   $0 run ${IMAGE_NAME}:${IMAGE_TAG}"
}

# Function to run Docker containers
run_docker() {
    local IMAGE_TO_RUN="${1:-}"
    local IMAGE_NAME="langflow"
    
    # If no image specified, list available images and prompt
    if [ -z "$IMAGE_TO_RUN" ]; then
        echo "� Available Langflow images:"
        docker images --filter "reference=${IMAGE_NAME}" --format "   {{.Repository}}:{{.Tag}} (created {{.CreatedSince}})"
        echo ""
        read -p "Enter image tag to run (copy/paste from above, e.g., langflow:1.4.2): " IMAGE_TO_RUN
        
        if [ -z "$IMAGE_TO_RUN" ]; then
            echo "❌ Error: No image tag provided"
            exit 1
        fi
    fi
    
    # Check if image exists
    if ! docker image inspect "$IMAGE_TO_RUN" >/dev/null 2>&1; then
        echo "❌ Error: Image '$IMAGE_TO_RUN' not found"
        echo ""
        echo "Available images:"
        docker images --filter "reference=${IMAGE_NAME}" --format "   {{.Repository}}:{{.Tag}}"
        exit 1
    fi
    
    echo "�🚀 Starting Docker containers with image: $IMAGE_TO_RUN"
    
    # Create network if it doesn't exist
    docker network inspect ${NETWORK_NAME} >/dev/null 2>&1 || \
        docker network create ${NETWORK_NAME}
    
    # Start Postgres container
    echo "🗄️  Starting Postgres container..."
    docker run -d \
        --name ${POSTGRES_CONTAINER} \
        --network ${NETWORK_NAME} \
        -e POSTGRES_DB=${POSTGRES_DB} \
        -e POSTGRES_USER=${POSTGRES_USER} \
        -e POSTGRES_PASSWORD=${POSTGRES_PASSWORD} \
        -p ${POSTGRES_PORT}:5432 \
        postgres:15.4
    
    # Wait for Postgres to be ready
    echo "⏳ Waiting for Postgres to be ready..."
    sleep 5
    
    # Start Langflow container with env-file
    echo "🌊 Starting Langflow container..."
    docker run -d \
        --name ${CONTAINER_NAME} \
        --network ${NETWORK_NAME} \
        --env-file .env-file \
        -e LANGFLOW_DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_CONTAINER}:5432/${POSTGRES_DB}" \
        -p 7860:7860 \
        ${IMAGE_TO_RUN}
    
    echo "✅ Containers started successfully"
    echo "🌐 Langflow: http://localhost:7860"
    echo "🗄️  Postgres: localhost:${POSTGRES_PORT}"
    echo "🏷️  Using image: ${IMAGE_TO_RUN}"
}

# Function to stop Docker containers
stop_docker() {
    echo "🛑 Stopping Docker containers..."
    
    # Stop and remove Langflow container
    docker stop ${CONTAINER_NAME} 2>/dev/null || true
    docker rm ${CONTAINER_NAME} 2>/dev/null || true
    
    # Stop and remove Postgres container
    docker stop ${POSTGRES_CONTAINER} 2>/dev/null || true
    docker rm ${POSTGRES_CONTAINER} 2>/dev/null || true
    
    # Remove network
    docker network rm ${NETWORK_NAME} 2>/dev/null || true
    
    echo "✅ Containers stopped and removed"
}

# Main script logic
case "${1:-}" in
    build)
        build_docker
        ;;
    run)
        run_docker "${2:-}"
        ;;
    stop)
        stop_docker
        ;;
    -h|--help)
        show_help
        ;;
    *)
        echo "❌ Error: Invalid command '${1:-}'"
        echo ""
        echo "Usage: $0 {build|run [IMAGE_TAG]|stop|-h|--help}"
        echo ""
        echo "Run '$0 --help' for more information"
        exit 1
        ;;
esac

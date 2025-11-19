#!/bin/bash

# Simple script for local Docker testing with Postgres
# Usage: ./local-docker-test.sh [build|run|stop]

set -e

# Determine which container engine to use. Default to docker but respect
# CONTAINER_ENGINE or DOCKER if the caller specifies podman.
CONTAINER_ENGINE="${CONTAINER_ENGINE:-${DOCKER:-docker}}"
export CONTAINER_ENGINE
export DOCKER="${CONTAINER_ENGINE}"

# Helper so every plain `docker` call honors the selected engine.
docker() {
    command "${CONTAINER_ENGINE}" "$@"
}

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

# Function to display simple help
show_help() {
    cat << 'EOF'
🐳 Local Docker Testing Script

📋 Usage:
    ./local-docker-test.sh [COMMAND] [OPTIONS]

🔧 Commands:
    build              Build Docker image (prompts for custom tag or uses timestamp)
    run [IMAGE_TAG]    Run Docker containers (prompts for port, default: 7860)
    stop              Stop Docker containers (interactive menu)
    -h, --help        Show this help message
    -v, --verbose     Show detailed help with examples

💡 Quick Start:
    export VITE_CLERK_PUBLISHABLE_KEY="pk_test_xxxxxxxxxxxx"
    ./local-docker-test.sh build
    ./local-docker-test.sh run
    ./local-docker-test.sh stop

📚 For detailed examples and options, run:
    ./local-docker-test.sh --verbose

EOF
}

# Function to display verbose help
show_verbose_help() {
    cat << 'EOF'
🐳 Local Docker Testing Script - Detailed Help

📋 Usage:
    ./local-docker-test.sh [COMMAND] [OPTIONS]

🔧 Commands:
    build              Build the Docker image with staging environment variables
    run [IMAGE_TAG]    Run Docker containers (Langflow + Postgres)
                      - If IMAGE_TAG is provided, uses that specific image
                      - If omitted, shows interactive menu to select from available images
    stop              Stop and remove Docker containers
    -h, --help        Show this help message
    -v, --verbose     Show this detailed help

📖 Description:
    This script helps you test the Langflow Docker container locally with Postgres.
    
    🔨 Build: Creates the Docker image using staging environment variables
              matching the GitHub workflow configuration.
              - Prompts for custom tag (e.g., branch name) or uses timestamp
              - Allows you to organize builds by feature/branch
    
    ▶️  Run:   Starts two containers:
              - Postgres database (custom port based on Langflow port)
              - Langflow application (custom port, default: 7860)
              - Prompts for port selection to allow multiple instances
              - Uses unique container names to avoid conflicts
              Interactive menu allows you to select from available images.
              Uses .env-file for runtime configuration.
    
    🛑 Stop:  Lists all running Langflow containers and provides options:
              - Stop ALL containers
              - Stop default containers only
              - Stop specific container by port
              Interactive menu for safe container management.

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
    
    # Build the Docker image with default timestamp tag
    ./local-docker-test.sh build
    
    # Build with custom tag (will be prompted)
    ./local-docker-test.sh build
    # (Select 'y' when asked, then enter tag like "feature-auth" or "v1.0.0")
    
    # Run the containers with a specific image on default port (7860)
    ./local-docker-test.sh run langflow:localbuild_20241008_120000
    # (Will be prompted for port selection)
    
    # Run the containers (will prompt for image selection and port)
    ./local-docker-test.sh run
    
    # Run multiple instances on different ports
    ./local-docker-test.sh run langflow:feature-auth
    # (Enter port 7860 for first instance)
    ./local-docker-test.sh run langflow:feature-xyz  
    # (Enter port 7861 for second instance)
    
    # Stop containers (interactive menu will be shown)
    ./local-docker-test.sh stop
    # (Choose option 1 to stop all, 2 for default, or 3 for specific port)
    
    # Alternative: Stop specific containers manually
    docker stop langflow-local-test-7861 langflow-postgres-local-7861

🌐 Access:
    Langflow UI:  http://localhost:[YOUR_SELECTED_PORT]
    Postgres DB:  localhost:[AUTO_CALCULATED_PORT] (user: langflow, password: langflow, db: langflow)

🔍 Troubleshooting:
    View container logs:
        docker logs langflow-local-test-[PORT]
        docker logs langflow-postgres-local-[PORT]
    
    Check running containers:
        docker ps
    
    List all Langflow containers:
        docker ps -a | grep langflow
    
    Stop specific instance by port:
        docker stop langflow-local-test-7861 langflow-postgres-local-7861
        docker rm langflow-local-test-7861 langflow-postgres-local-7861

📝 Notes:
    - Multiple instances can run simultaneously on different ports
    - Each instance gets unique container and network names based on the port
    - Postgres port is auto-calculated: 5432 + (Langflow_port - 7860)
      Example: Langflow on 7861 → Postgres on 5433
    - Custom tags help organize builds by feature/branch/version

EOF
}

# Function to display commands in a nice UI
display_command() {
    local cmd="$1"
    local description="${2:-}"
    
    echo ""
    echo "┌─────────────────────────────────────────────────────────────────"
    if [ -n "$description" ]; then
        echo "│ 💻 $description"
        echo "├─────────────────────────────────────────────────────────────────"
    fi
    echo "│ $ $cmd"
    echo "└─────────────────────────────────────────────────────────────────"
    echo ""
}

# Function to display multi-line commands
display_multiline_command() {
    local description="$1"
    shift
    local commands=("$@")
    
    echo ""
    echo "┌─────────────────────────────────────────────────────────────────"
    echo "│ 💻 $description"
    echo "├─────────────────────────────────────────────────────────────────"
    for cmd in "${commands[@]}"; do
        echo "│ $ $cmd"
    done
    echo "└─────────────────────────────────────────────────────────────────"
    echo ""
}

# Check if VITE_CLERK_PUBLISHABLE_KEY is set
check_clerk_envs() {
    local missing=false

    echo ""
    echo "🔍 Checking Clerk environment variables..."

    if [ -z "${VITE_CLERK_PUBLISHABLE_KEY:-}" ] && [ -z "${VITE_CLERK_FRONTEND_API:-}" ]; then
        echo "❌ Both Clerk environment variables are missing!"
        echo ""
        echo "You must set both before continuing:"
        echo "    export VITE_CLERK_PUBLISHABLE_KEY=\"pk_test_your_key_here\""
        echo "    export VITE_CLERK_FRONTEND_API=\"clerk.yourapp.dev\""
        echo ""
        echo "💡 Example:"
        echo "    export VITE_CLERK_PUBLISHABLE_KEY=\"pk_test_12345ABCDE\""
        echo "    export VITE_CLERK_FRONTEND_API=\"clerk.localhost.dev\""
        echo ""
        missing=true

    elif [ -z "${VITE_CLERK_PUBLISHABLE_KEY:-}" ]; then
        echo "❌ VITE_CLERK_PUBLISHABLE_KEY is missing!"
        echo "✅ VITE_CLERK_FRONTEND_API is set to: ${VITE_CLERK_FRONTEND_API}"
        echo ""
        echo "Set it using:"
        echo "    export VITE_CLERK_PUBLISHABLE_KEY=\"pk_test_your_key_here\""
        echo ""
        missing=true

    elif [ -z "${VITE_CLERK_FRONTEND_API:-}" ]; then
        echo "❌ VITE_CLERK_FRONTEND_API is missing!"
        echo "✅ VITE_CLERK_PUBLISHABLE_KEY is set"
        echo ""
        echo "Set it using:"
        echo "    export VITE_CLERK_FRONTEND_API=\"clerk.yourapp.dev\""
        echo ""
        echo "💡 Example:"
        echo "    export VITE_CLERK_FRONTEND_API=\"clerk.localhost.dev\""
        echo ""
        missing=true

    else
        echo "✅ Both Clerk environment variables are set"
        echo "   - VITE_CLERK_PUBLISHABLE_KEY: ${VITE_CLERK_PUBLISHABLE_KEY}"
        echo "   - VITE_CLERK_FRONTEND_API: ${VITE_CLERK_FRONTEND_API}"
    fi

    if [ "$missing" = true ]; then
        echo ""
        echo "❌ Please fix the missing variables above before continuing."
        echo ""
        exit 1
    fi
}

# Configuration from GitHub workflow (staging environment)
VITE_AUTO_LOGIN=false
VITE_CLERK_AUTH_ENABLED=true
VITE_CLERK_PUBLISHABLE_KEY="${VITE_CLERK_PUBLISHABLE_KEY:-}"
VITE_CLERK_FRONTEND_API="${VITE_CLERK_FRONTEND_API:-}"

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
    # Check Clerk environment variables together
    check_clerk_envs

    # Ask for custom tag
    echo ""
    echo "🏷️  Docker Image Tagging"
    
    # Calculate default tag once to ensure consistency
    DEFAULT_TAG="localbuild_$(date +%Y%m%d_%H%M%S)"
    
    echo "   Default tag: ${DEFAULT_TAG}"
    echo ""
    read -p "Press ENTER for default tag <${DEFAULT_TAG}>, or enter your custom tag: " CUSTOM_TAG
    
    if [ -n "$CUSTOM_TAG" ]; then
        # Get current branch name for reference
        CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
        echo ""
        echo "📌 Current branch: ${CURRENT_BRANCH}"
        
        display_command "echo \"$CUSTOM_TAG\" | sed 's/[^a-zA-Z0-9._-]/_/g'" "Sanitizing custom tag name"
        
        # Sanitize tag name (replace invalid characters)
        CUSTOM_TAG=$(echo "$CUSTOM_TAG" | sed 's/[^a-zA-Z0-9._-]/_/g')
        IMAGE_TAG="$CUSTOM_TAG"
        echo "✅ Using custom tag: ${IMAGE_TAG}"
    else
        IMAGE_TAG="$DEFAULT_TAG"
        echo "✅ Using default tag: ${IMAGE_TAG}"
    fi
    
    echo ""
    echo "🔨 Building Docker image with tag: ${IMAGE_NAME}:${IMAGE_TAG}"
    
    BUILD_CMD="TAG=\"${IMAGE_NAME}:${IMAGE_TAG}\" DOCKER_BUILDKIT=1 \
    VITE_AUTO_LOGIN=${VITE_AUTO_LOGIN} \
    VITE_CLERK_AUTH_ENABLED=${VITE_CLERK_AUTH_ENABLED} \
    VITE_CLERK_PUBLISHABLE_KEY=${VITE_CLERK_PUBLISHABLE_KEY} \
    VITE_CLERK_FRONTEND_API=${VITE_CLERK_FRONTEND_API} \
    make docker_build"
    display_command "$BUILD_CMD" "Building Docker image"

    TAG="${IMAGE_NAME}:${IMAGE_TAG}" \
    DOCKER_BUILDKIT=1 \
    VITE_AUTO_LOGIN=${VITE_AUTO_LOGIN} \
    VITE_CLERK_AUTH_ENABLED=${VITE_CLERK_AUTH_ENABLED} \
    VITE_CLERK_PUBLISHABLE_KEY=${VITE_CLERK_PUBLISHABLE_KEY} \
    VITE_CLERK_FRONTEND_API=${VITE_CLERK_FRONTEND_API} \
    make docker_build
    
    echo ""
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
        echo "📋 Available Langflow images:"
        display_command "docker images --filter \"reference=${IMAGE_NAME}\" --format \"{{.Repository}}:{{.Tag}} (created {{.CreatedSince}})\"" "Listing available Langflow images"
        docker images --filter "reference=${IMAGE_NAME}" --format "   {{.Repository}}:{{.Tag}} (created {{.CreatedSince}})"
        echo ""
        read -p "Enter image tag to run (copy/paste from above, e.g., langflow:1.4.2): " IMAGE_TO_RUN
        
        if [ -z "$IMAGE_TO_RUN" ]; then
            echo "❌ Error: No image tag provided"
            exit 1
        fi
    fi
    
    # Check if image exists
    display_command "docker image inspect \"$IMAGE_TO_RUN\"" "Verifying image exists"
    if ! docker image inspect "$IMAGE_TO_RUN" >/dev/null 2>&1; then
        echo "❌ Error: Image '$IMAGE_TO_RUN' not found"
        echo ""
        echo "Available images:"
        docker images --filter "reference=${IMAGE_NAME}" --format "   {{.Repository}}:{{.Tag}}"
        exit 1
    fi
    
    # Ask for host port
    echo ""
    echo "🔌 Port Configuration"
    read -p "Enter host port for Langflow (default: 7860): " LANGFLOW_HOST_PORT
    LANGFLOW_HOST_PORT=${LANGFLOW_HOST_PORT:-7860}
    
    # Check if containers are already running on this port
    EXISTING_LANGFLOW_CONTAINER=$(docker ps -a --filter "name=langflow-local-test-${LANGFLOW_HOST_PORT}" --format "{{.Names}}" 2>/dev/null)
    EXISTING_POSTGRES_CONTAINER=$(docker ps -a --filter "name=langflow-postgres-local-${LANGFLOW_HOST_PORT}" --format "{{.Names}}" 2>/dev/null)
    
    if [ -n "$EXISTING_LANGFLOW_CONTAINER" ] || [ -n "$EXISTING_POSTGRES_CONTAINER" ]; then
        echo ""
        echo "⚠️  Containers already exist on port ${LANGFLOW_HOST_PORT}:"
        [ -n "$EXISTING_LANGFLOW_CONTAINER" ] && echo "   • $EXISTING_LANGFLOW_CONTAINER"
        [ -n "$EXISTING_POSTGRES_CONTAINER" ] && echo "   • $EXISTING_POSTGRES_CONTAINER"
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "🔧 PORT CONFLICT OPTIONS"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "   Press ENTER to stop existing containers and start new one on port ${LANGFLOW_HOST_PORT}"
        echo ""
        echo "   1. Choose a different port"
        echo "   2. Stop containers manually and exit"
        echo "   3. Cancel (do nothing)"
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        read -p "👉 Press ENTER to stop container running on port ${LANGFLOW_HOST_PORT}, or enter option (1, 2, 3): " PORT_CONFLICT_CHOICE
        
        case "$PORT_CONFLICT_CHOICE" in
            "")
                # Stop existing containers
                echo ""
                echo "🛑 Stopping existing containers on port ${LANGFLOW_HOST_PORT}..."
                
                # Get the Langflow image before stopping (to remove it later)
                LANGFLOW_IMAGE=""
                if [ -n "$EXISTING_LANGFLOW_CONTAINER" ]; then
                    LANGFLOW_IMAGE=$(docker inspect --format='{{.Config.Image}}' "$EXISTING_LANGFLOW_CONTAINER" 2>/dev/null || true)
                    
                    STOP_CMD="docker stop \"$EXISTING_LANGFLOW_CONTAINER\" && docker rm \"$EXISTING_LANGFLOW_CONTAINER\""
                    display_command "$STOP_CMD" "Stopping and removing $EXISTING_LANGFLOW_CONTAINER"
                    docker stop "$EXISTING_LANGFLOW_CONTAINER" 2>/dev/null || true
                    docker rm "$EXISTING_LANGFLOW_CONTAINER" 2>/dev/null || true
                fi
                
                if [ -n "$EXISTING_POSTGRES_CONTAINER" ]; then
                    POSTGRES_STOP_CMD="docker stop \"$EXISTING_POSTGRES_CONTAINER\" && docker rm \"$EXISTING_POSTGRES_CONTAINER\""
                    display_command "$POSTGRES_STOP_CMD" "Stopping and removing $EXISTING_POSTGRES_CONTAINER"
                    docker stop "$EXISTING_POSTGRES_CONTAINER" 2>/dev/null || true
                    docker rm "$EXISTING_POSTGRES_CONTAINER" 2>/dev/null || true
                fi
                
                # Remove the network
                NETWORK_TO_REMOVE="langflow-test-network-${LANGFLOW_HOST_PORT}"
                NETWORK_RM_CMD="docker network rm \"$NETWORK_TO_REMOVE\""
                display_command "$NETWORK_RM_CMD" "Removing network"
                docker network rm "$NETWORK_TO_REMOVE" 2>/dev/null || true
                
                # Automatically remove old image if it was a localbuild
                if [ -n "$LANGFLOW_IMAGE" ]; then
                    if [[ "$LANGFLOW_IMAGE" == langflow:localbuild_* ]]; then
                        echo ""
                        echo "🗑️  Old local build image detected: $LANGFLOW_IMAGE"
                        echo "   Removing to free disk space..."
                        IMG_RM_CMD="docker rmi \"$LANGFLOW_IMAGE\""
                        display_command "$IMG_RM_CMD" "Removing old image to free up space"
                        docker rmi "$LANGFLOW_IMAGE" 2>/dev/null || true
                        echo "✅ Removed old local build image: $LANGFLOW_IMAGE"
                    else
                        echo "ℹ️  Skipping image removal (non-local build): $LANGFLOW_IMAGE"
                    fi
                fi
                
                echo "✅ Existing containers stopped. Proceeding with new containers..."
                echo ""
                ;;
            1)
                # Choose different port
                echo ""
                read -p "Enter a different port: " LANGFLOW_HOST_PORT
                if [ -z "$LANGFLOW_HOST_PORT" ]; then
                    echo "❌ Error: No port provided"
                    exit 1
                fi
                
                # Re-check if new port also has conflicts (recursive check)
                EXISTING_LANGFLOW_CONTAINER=$(docker ps -a --filter "name=langflow-local-test-${LANGFLOW_HOST_PORT}" --format "{{.Names}}" 2>/dev/null)
                EXISTING_POSTGRES_CONTAINER=$(docker ps -a --filter "name=langflow-postgres-local-${LANGFLOW_HOST_PORT}" --format "{{.Names}}" 2>/dev/null)
                
                if [ -n "$EXISTING_LANGFLOW_CONTAINER" ] || [ -n "$EXISTING_POSTGRES_CONTAINER" ]; then
                    echo "⚠️  Port ${LANGFLOW_HOST_PORT} also has existing containers!"
                    echo "   Please run the script again and choose an available port."
                    exit 1
                fi
                
                echo "✅ Using port ${LANGFLOW_HOST_PORT}"
                echo ""
                ;;
            2)
                # Manual stop
                echo ""
                echo "💡 To stop containers manually, run:"
                echo ""
                echo "   ./$(basename $0) stop"
                echo ""
                echo "   Then run this command again."
                exit 0
                ;;
            3|cancel|CANCEL)
                echo "❌ Cancelled - no changes made"
                exit 0
                ;;
            *)
                echo "❌ Invalid option"
                exit 1
                ;;
        esac
    fi
    
    # Additional check: Port might be in use by non-Docker process
    if lsof -Pi :${LANGFLOW_HOST_PORT} -sTCP:LISTEN -t >/dev/null 2>&1 || netstat -an 2>/dev/null | grep -q ":${LANGFLOW_HOST_PORT}.*LISTEN"; then
        echo "⚠️  Warning: Port ${LANGFLOW_HOST_PORT} appears to be in use by another process (not a Docker container)"
        echo "   This might be a different service"
        read -p "   Do you want to continue anyway? (y/N): " CONTINUE_ANYWAY
        if [[ ! "$CONTINUE_ANYWAY" =~ ^[Yy]$ ]]; then
            echo "❌ Aborted. Please choose a different port or stop the service using port ${LANGFLOW_HOST_PORT}"
            exit 1
        fi
    fi
    
    # Use unique container names based on port to allow multiple instances
    local UNIQUE_CONTAINER_NAME="${CONTAINER_NAME}-${LANGFLOW_HOST_PORT}"
    local UNIQUE_POSTGRES_CONTAINER="${POSTGRES_CONTAINER}-${LANGFLOW_HOST_PORT}"
    local UNIQUE_NETWORK_NAME="${NETWORK_NAME}-${LANGFLOW_HOST_PORT}"
    local UNIQUE_POSTGRES_PORT=$((5432 + LANGFLOW_HOST_PORT - 7860))
    
    # Volume names based on port for multi-instance support
    local POSTGRES_VOLUME_NAME="langflow_postgres_data_${LANGFLOW_HOST_PORT}"
    local LANGFLOW_VOLUME_NAME="langflow_config_${LANGFLOW_HOST_PORT}"
    
    echo ""
    echo "🚀 Starting Docker containers with image: $IMAGE_TO_RUN"
    echo "🔌 Langflow will be available on port: ${LANGFLOW_HOST_PORT}"
    echo "🗄️  Postgres will be available on port: ${UNIQUE_POSTGRES_PORT}"
    echo "💾 PostgreSQL volume: ${POSTGRES_VOLUME_NAME}"
    echo "💾 Langflow config volume: ${LANGFLOW_VOLUME_NAME}"
    
    # Create network if it doesn't exist
    NETWORK_CMD="docker network create ${UNIQUE_NETWORK_NAME}"
    display_command "$NETWORK_CMD" "Creating Docker network (if not exists)"
    docker network inspect ${UNIQUE_NETWORK_NAME} >/dev/null 2>&1 || \
        docker network create ${UNIQUE_NETWORK_NAME}
    
    # Start Postgres container with volume for data persistence
    echo "🗄️  Starting Postgres container with persistent volume..."
    POSTGRES_CMD="docker run -d --name ${UNIQUE_POSTGRES_CONTAINER} --network ${UNIQUE_NETWORK_NAME} -e POSTGRES_DB=${POSTGRES_DB} -e POSTGRES_USER=${POSTGRES_USER} -e POSTGRES_PASSWORD=${POSTGRES_PASSWORD} -p ${UNIQUE_POSTGRES_PORT}:5432 -v ${POSTGRES_VOLUME_NAME}:/var/lib/postgresql/data postgres:15.4"
    display_command "$POSTGRES_CMD" "Starting Postgres container"
    
    docker run -d \
        --name ${UNIQUE_POSTGRES_CONTAINER} \
        --network ${UNIQUE_NETWORK_NAME} \
        -e POSTGRES_DB=${POSTGRES_DB} \
        -e POSTGRES_USER=${POSTGRES_USER} \
        -e POSTGRES_PASSWORD=${POSTGRES_PASSWORD} \
        -p ${UNIQUE_POSTGRES_PORT}:5432 \
        -v ${POSTGRES_VOLUME_NAME}:/var/lib/postgresql/data \
        postgres:15.4
    
    # Wait for Postgres to be ready
    echo "⏳ Waiting for Postgres to be ready..."
    display_command "sleep 5" "Waiting for Postgres initialization"
    sleep 5
    
    # Start Langflow container with env-file and persistent volumes
    echo ""
    echo "🌊 Starting Langflow container with persistent config volume..."
    LANGFLOW_CMD="docker run -d --name ${UNIQUE_CONTAINER_NAME} --network ${UNIQUE_NETWORK_NAME} --env-file .env-file -e LANGFLOW_DATABASE_URL=\"postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${UNIQUE_POSTGRES_CONTAINER}:5432/${POSTGRES_DB}\" -e LANGFLOW_CONFIG_DIR=\"/var/lib/langflow\" -e LANGFLOW_SAVE_DB_IN_CONFIG_DIR=\"false\" --user root -p ${LANGFLOW_HOST_PORT}:7860 -v ${LANGFLOW_VOLUME_NAME}:/var/lib/langflow ${IMAGE_TO_RUN}"
    display_command "$LANGFLOW_CMD" "Starting Langflow container"
    
    docker run -d \
        --name ${UNIQUE_CONTAINER_NAME} \
        --network ${UNIQUE_NETWORK_NAME} \
        --env-file .env-file \
        -e LANGFLOW_DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${UNIQUE_POSTGRES_CONTAINER}:5432/${POSTGRES_DB}" \
        -e LANGFLOW_CONFIG_DIR="/var/lib/langflow" \
        -e LANGFLOW_SAVE_DB_IN_CONFIG_DIR="false" \
        --user root \
        -p ${LANGFLOW_HOST_PORT}:7860 \
        -v ${LANGFLOW_VOLUME_NAME}:/var/lib/langflow \
        ${IMAGE_TO_RUN}
    
    # Wait for Langflow to be ready and accessible
    echo ""
    echo "⏳ Waiting for Langflow application to be ready..."
    MAX_RETRIES=30
    RETRY_COUNT=0
    LANGFLOW_URL="http://localhost:${LANGFLOW_HOST_PORT}"
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if curl -sf "${LANGFLOW_URL}/" > /dev/null 2>&1; then
            echo "✅ Langflow is ready and accessible!"
            break
        fi
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
            echo "⚠️  Warning: Langflow did not become accessible within expected time"
            echo "   Container may still be initializing. Check logs with: docker logs ${UNIQUE_CONTAINER_NAME}"
        else
            echo -n "."
            sleep 2
        fi
    done
    
    echo ""
    echo "✅ Containers started successfully with persistent volumes"
    echo "🌐 Langflow: http://localhost:${LANGFLOW_HOST_PORT}"
    echo "🗄️  Postgres: localhost:${UNIQUE_POSTGRES_PORT}"
    echo "🏷️  Using image: ${IMAGE_TO_RUN}"
    echo "📦 Container: ${UNIQUE_CONTAINER_NAME}"
    echo ""
    echo "💾 Persistent Volumes (data survives container restarts):"
    echo "   📊 PostgreSQL data: ${POSTGRES_VOLUME_NAME}"
    echo "   ⚙️  Langflow config: ${LANGFLOW_VOLUME_NAME}"
    echo ""
    echo "💡 To view logs: docker logs ${UNIQUE_CONTAINER_NAME}"
    echo "💡 To stop this instance: docker stop ${UNIQUE_CONTAINER_NAME} ${UNIQUE_POSTGRES_CONTAINER}"
    echo "💡 To remove volumes: docker volume rm ${POSTGRES_VOLUME_NAME} ${LANGFLOW_VOLUME_NAME}"
}

# Function to stop Docker containers
stop_docker() {
    echo "🛑 Stopping Docker containers..."
    echo ""
    
    # List all Langflow-related containers (running and stopped)
    echo "📋 List of containers:"
    
    LIST_LANGFLOW_CMD="docker ps -a --filter \"name=langflow-local-test\" --format \"{{.Names}}\t{{.State}}\t{{.Ports}}\t{{.Image}}\""
    LIST_POSTGRES_CMD="docker ps -a --filter \"name=langflow-postgres-local\" --format \"{{.Names}}\t{{.State}}\t{{.Image}}\""
    
    display_multiline_command "Listing containers" "$LIST_LANGFLOW_CMD" "$LIST_POSTGRES_CMD"
    
    LANGFLOW_CONTAINERS=$(docker ps -a --filter "name=langflow-local-test" --format "{{.Names}}\t{{.State}}\t{{.Ports}}\t{{.Image}}")
    POSTGRES_CONTAINERS=$(docker ps -a --filter "name=langflow-postgres-local" --format "{{.Names}}\t{{.State}}\t{{.Image}}")
    
    if [ -z "$LANGFLOW_CONTAINERS" ] && [ -z "$POSTGRES_CONTAINERS" ]; then
        echo "   No containers found"
        return 0
    fi
    
    # Display containers with numbering for easy selection
    declare -a CONTAINER_LIST
    declare -a CONTAINER_NAMES
    INDEX=1
    
    if [ -n "$LANGFLOW_CONTAINERS" ]; then
        echo ""
        echo "   Application containers:"
        while IFS=$'\t' read -r name state ports image; do
            CONTAINER_LIST[$INDEX]="$name"
            CONTAINER_NAMES[$INDEX]="$name"
            if [ -n "$ports" ]; then
                echo "    ${INDEX}. $name ($state) | Image: $image | Ports: $ports"
            else
                echo "    ${INDEX}. $name ($state) | Image: $image"
            fi
            INDEX=$((INDEX + 1))
        done <<< "$LANGFLOW_CONTAINERS"
    fi
    
    if [ -n "$POSTGRES_CONTAINERS" ]; then
        echo ""
        echo "   Database containers:"
        while IFS=$'\t' read -r name state image; do
            echo "      • $name ($state) | Image: $image"
        done <<< "$POSTGRES_CONTAINERS"
    fi
    
    # Check for local build containers
    LOCALBUILD_CONTAINERS=$(docker ps -a --filter "name=langflow-local-test" --format "{{.Names}}" | grep -E "langflow-local-test-[0-9]+" || true)
    LOCALBUILD_COUNT=$(echo "$LOCALBUILD_CONTAINERS" | grep -v '^$' | wc -l)
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔧 STOP OPTIONS - What would you like to stop?"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if [ -n "$LOCALBUILD_CONTAINERS" ] && [ "$LOCALBUILD_COUNT" -gt 0 ]; then
        echo ""
        echo "   Press ENTER to stop the local build containers (${LOCALBUILD_COUNT} containers)"
        echo ""
        echo "   1. Stop ALL containers (everything)"
        echo "   2. Select a specific container by number from the list above"
        echo "   3. Cancel (do nothing)"
    else
        echo ""
        echo "   1. Stop ALL containers (everything)"
        echo "   2. Select a specific container by number from the list above"
        echo "   3. Cancel (do nothing)"
    fi
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    read -p "👉 Press ENTER to stop localbuild containers, or enter option (1, 2, 3): " STOP_CHOICE
    
    # Handle the choice based on whether we have local build containers
    if [ -n "$LOCALBUILD_CONTAINERS" ] && [ "$LOCALBUILD_COUNT" -gt 0 ]; then
        # Menu with local build containers present
        case "$STOP_CHOICE" in
            ""|localbuild)
                # Stop all local build containers only (default when pressing Enter)
                echo "🛑 Stopping all local build containers..."
                echo ""
                
                # Stop and remove each local build container and its postgres
                echo "$LOCALBUILD_CONTAINERS" | while read -r container_name; do
                    if [ -n "$container_name" ]; then
                        # Extract port from container name
                        PORT=$(echo "$container_name" | grep -oE '[0-9]+$')
                        POSTGRES_NAME="langflow-postgres-local-${PORT}"
                        NETWORK_NAME="langflow-test-network-${PORT}"
                        
                        # Get the image name before stopping the container (only for Langflow, not Postgres)
                        LANGFLOW_IMAGE=$(docker inspect --format='{{.Config.Image}}' "$container_name" 2>/dev/null || true)
                        
                        echo "   Stopping $container_name and $POSTGRES_NAME..."
                        
                        STOP_CMD="docker stop \"$container_name\" && docker rm \"$container_name\""
                        display_command "$STOP_CMD" "Stopping and removing $container_name"
                        docker stop "$container_name" 2>/dev/null || true
                        docker rm "$container_name" 2>/dev/null || true
                        
                        POSTGRES_STOP_CMD="docker stop \"$POSTGRES_NAME\" && docker rm \"$POSTGRES_NAME\""
                        display_command "$POSTGRES_STOP_CMD" "Stopping and removing $POSTGRES_NAME"
                        docker stop "$POSTGRES_NAME" 2>/dev/null || true
                        docker rm "$POSTGRES_NAME" 2>/dev/null || true
                        
                        NETWORK_RM_CMD="docker network rm \"$NETWORK_NAME\""
                        display_command "$NETWORK_RM_CMD" "Removing network $NETWORK_NAME"
                        docker network rm "$NETWORK_NAME" 2>/dev/null || true
                        
                        # Remove only the Langflow image (not postgres:15.4)
                        if [ -n "$LANGFLOW_IMAGE" ] && [[ ! "$LANGFLOW_IMAGE" =~ ^postgres: ]]; then
                            echo "   Removing image: $LANGFLOW_IMAGE"
                            IMG_RM_CMD="docker rmi \"$LANGFLOW_IMAGE\""
                            display_command "$IMG_RM_CMD" "Removing image"
                            docker rmi "$LANGFLOW_IMAGE" 2>/dev/null || true
                        fi
                        echo ""
                    fi
                done
                
                echo "✅ All local build containers stopped and removed"
                ;;
            1)
                # Stop ALL containers
                echo "🛑 Stopping ALL containers..."
                echo ""
                
                # Collect only Langflow images (not postgres)
                declare -a LANGFLOW_IMAGES
                while IFS= read -r container_name; do
                    if [ -n "$container_name" ]; then
                        IMAGE=$(docker inspect --format='{{.Config.Image}}' "$container_name" 2>/dev/null || true)
                        if [ -n "$IMAGE" ] && [[ ! "$IMAGE" =~ ^postgres: ]]; then
                            LANGFLOW_IMAGES+=("$IMAGE")
                        fi
                    fi
                done < <(docker ps -a --filter "name=langflow-local-test" --format "{{.Names}}")
                
                # Stop all containers
                STOP_LANGFLOW_CMD="docker ps -a --filter \"name=langflow-local-test\" --format \"{{.Names}}\" | xargs -r docker stop"
                display_command "$STOP_LANGFLOW_CMD" "Stopping all application containers"
                docker ps -a --filter "name=langflow-local-test" --format "{{.Names}}" | xargs -r docker stop 2>/dev/null || true
                
                STOP_POSTGRES_CMD="docker ps -a --filter \"name=langflow-postgres-local\" --format \"{{.Names}}\" | xargs -r docker stop"
                display_command "$STOP_POSTGRES_CMD" "Stopping all database containers"
                docker ps -a --filter "name=langflow-postgres-local" --format "{{.Names}}" | xargs -r docker stop 2>/dev/null || true
                
                # Remove all containers
                RM_LANGFLOW_CMD="docker ps -a --filter \"name=langflow-local-test\" --format \"{{.Names}}\" | xargs -r docker rm"
                display_command "$RM_LANGFLOW_CMD" "Removing application containers"
                docker ps -a --filter "name=langflow-local-test" --format "{{.Names}}" | xargs -r docker rm 2>/dev/null || true
                
                RM_POSTGRES_CMD="docker ps -a --filter \"name=langflow-postgres-local\" --format \"{{.Names}}\" | xargs -r docker rm"
                display_command "$RM_POSTGRES_CMD" "Removing database containers"
                docker ps -a --filter "name=langflow-postgres-local" --format "{{.Names}}" | xargs -r docker rm 2>/dev/null || true
                
                # Remove all networks
                RM_NETWORKS_CMD="docker network ls --filter \"name=langflow-test-network\" --format \"{{.Name}}\" | xargs -r docker network rm"
                display_command "$RM_NETWORKS_CMD" "Removing networks"
                docker network ls --filter "name=langflow-test-network" --format "{{.Name}}" | xargs -r docker network rm 2>/dev/null || true
                
                # Remove only Langflow images (not postgres)
                if [ ${#LANGFLOW_IMAGES[@]} -gt 0 ]; then
                    echo "   Removing images..."
                    printf '%s\n' "${LANGFLOW_IMAGES[@]}" | sort -u | while read -r image; do
                        if [ -n "$image" ]; then
                            echo "   Removing image: $image"
                            IMG_RM_CMD="docker rmi \"$image\""
                            display_command "$IMG_RM_CMD" "Removing image"
                            docker rmi "$image" 2>/dev/null || true
                        fi
                    done
                fi
                
                echo ""
                echo "✅ All containers and images stopped and removed"
                ;;
            2)
                # Select specific container by number
                read -p "Enter container number from the list: " CONTAINER_NUM
                if [ -n "${CONTAINER_NAMES[$CONTAINER_NUM]}" ]; then
                    stop_specific_container "${CONTAINER_NAMES[$CONTAINER_NUM]}"
                else
                    echo "❌ Invalid container number: $CONTAINER_NUM"
                    return 1
                fi
                ;;
            3|cancel|CANCEL)
                echo "❌ Cancelled - no containers stopped"
                return 0
                ;;
            *)
                # Check if it's a valid container number from the original list
                if [[ "$STOP_CHOICE" =~ ^[0-9]+$ ]] && [ -n "${CONTAINER_NAMES[$STOP_CHOICE]}" ]; then
                    stop_specific_container "${CONTAINER_NAMES[$STOP_CHOICE]}"
                else
                    echo "❌ Invalid option. Please enter 1, 2, 3, or press ENTER"
                    return 1
                fi
                ;;
        esac
    else
        # Menu without local build containers
        case "$STOP_CHOICE" in
            1)
                # Stop ALL containers
                echo "🛑 Stopping ALL containers..."
                echo ""
                
                # Collect only Langflow images (not postgres)
                declare -a LANGFLOW_IMAGES
                while IFS= read -r container_name; do
                    if [ -n "$container_name" ]; then
                        IMAGE=$(docker inspect --format='{{.Config.Image}}' "$container_name" 2>/dev/null || true)
                        if [ -n "$IMAGE" ] && [[ ! "$IMAGE" =~ ^postgres: ]]; then
                            LANGFLOW_IMAGES+=("$IMAGE")
                        fi
                    fi
                done < <(docker ps -a --filter "name=langflow-local-test" --format "{{.Names}}")
                
                # Stop all containers
                STOP_LANGFLOW_CMD="docker ps -a --filter \"name=langflow-local-test\" --format \"{{.Names}}\" | xargs -r docker stop"
                display_command "$STOP_LANGFLOW_CMD" "Stopping all application containers"
                docker ps -a --filter "name=langflow-local-test" --format "{{.Names}}" | xargs -r docker stop 2>/dev/null || true
                
                STOP_POSTGRES_CMD="docker ps -a --filter \"name=langflow-postgres-local\" --format \"{{.Names}}\" | xargs -r docker stop"
                display_command "$STOP_POSTGRES_CMD" "Stopping all database containers"
                docker ps -a --filter "name=langflow-postgres-local" --format "{{.Names}}" | xargs -r docker stop 2>/dev/null || true
                
                # Remove all containers
                RM_LANGFLOW_CMD="docker ps -a --filter \"name=langflow-local-test\" --format \"{{.Names}}\" | xargs -r docker rm"
                display_command "$RM_LANGFLOW_CMD" "Removing application containers"
                docker ps -a --filter "name=langflow-local-test" --format "{{.Names}}" | xargs -r docker rm 2>/dev/null || true
                
                RM_POSTGRES_CMD="docker ps -a --filter \"name=langflow-postgres-local\" --format \"{{.Names}}\" | xargs -r docker rm"
                display_command "$RM_POSTGRES_CMD" "Removing database containers"
                docker ps -a --filter "name=langflow-postgres-local" --format "{{.Names}}" | xargs -r docker rm 2>/dev/null || true
                
                # Remove all networks
                RM_NETWORKS_CMD="docker network ls --filter \"name=langflow-test-network\" --format \"{{.Name}}\" | xargs -r docker network rm"
                display_command "$RM_NETWORKS_CMD" "Removing networks"
                docker network ls --filter "name=langflow-test-network" --format "{{.Name}}" | xargs -r docker network rm 2>/dev/null || true
                
                # Remove only Langflow images (not postgres)
                if [ ${#LANGFLOW_IMAGES[@]} -gt 0 ]; then
                    echo "   Removing images..."
                    printf '%s\n' "${LANGFLOW_IMAGES[@]}" | sort -u | while read -r image; do
                        if [ -n "$image" ]; then
                            echo "   Removing image: $image"
                            IMG_RM_CMD="docker rmi \"$image\""
                            display_command "$IMG_RM_CMD" "Removing image"
                            docker rmi "$image" 2>/dev/null || true
                        fi
                    done
                fi
                
                echo ""
                echo "✅ All containers and images stopped and removed"
                ;;
            2)
                # Select specific container by number
                read -p "Enter container number from the list: " CONTAINER_NUM
                if [ -n "${CONTAINER_NAMES[$CONTAINER_NUM]}" ]; then
                    stop_specific_container "${CONTAINER_NAMES[$CONTAINER_NUM]}"
                else
                    echo "❌ Invalid container number: $CONTAINER_NUM"
                    return 1
                fi
                ;;
            3|cancel|CANCEL)
                echo "❌ Cancelled - no containers stopped"
                return 0
                ;;
            *)
                # Check if it's a valid container number from the original list
                if [[ "$STOP_CHOICE" =~ ^[0-9]+$ ]] && [ -n "${CONTAINER_NAMES[$STOP_CHOICE]}" ]; then
                    stop_specific_container "${CONTAINER_NAMES[$STOP_CHOICE]}"
                else
                    echo "❌ Invalid option. Please enter 1, 2, or 3"
                    return 1
                fi
                ;;
        esac
    fi
}

# Helper function to stop a specific container
stop_specific_container() {
    local SELECTED_CONTAINER="$1"
    
    # Get the image name before stopping (only Langflow, not Postgres)
    LANGFLOW_IMAGE=$(docker inspect --format='{{.Config.Image}}' "$SELECTED_CONTAINER" 2>/dev/null || true)
    
    # Extract port from container name if it exists
    if [[ "$SELECTED_CONTAINER" =~ -([0-9]+)$ ]]; then
        PORT="${BASH_REMATCH[1]}"
        POSTGRES_NAME="langflow-postgres-local-${PORT}"
        NETWORK_NAME="langflow-test-network-${PORT}"
    else
        # Default containers without port suffix
        POSTGRES_NAME="langflow-postgres-local"
        NETWORK_NAME="langflow-test-network"
    fi
    
    echo "🛑 Stopping container: $SELECTED_CONTAINER and $POSTGRES_NAME..."
    
    docker stop "$SELECTED_CONTAINER" 2>/dev/null || true
    docker rm "$SELECTED_CONTAINER" 2>/dev/null || true
    docker stop "$POSTGRES_NAME" 2>/dev/null || true
    docker rm "$POSTGRES_NAME" 2>/dev/null || true
    docker network rm "$NETWORK_NAME" 2>/dev/null || true
    
    # Remove only the Langflow image (not postgres:15.4)
    if [ -n "$LANGFLOW_IMAGE" ] && [[ ! "$LANGFLOW_IMAGE" =~ ^postgres: ]]; then
        echo "🗑️  Removing Langflow image: $LANGFLOW_IMAGE"
        IMG_RM_CMD="docker rmi \"$LANGFLOW_IMAGE\""
        display_command "$IMG_RM_CMD" "Removing image to free up space"
        docker rmi "$LANGFLOW_IMAGE" 2>/dev/null || true
    fi
    
    echo "✅ Container $SELECTED_CONTAINER stopped and removed"
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
    -v|--verbose)
        show_verbose_help
        ;;
    *)
        echo "❌ Error: Invalid command '${1:-}'"
        echo ""
        echo "Usage: $0 {build|run [IMAGE_TAG]|stop|-h|--help|-v|--verbose}"
        echo ""
        echo "Run '$0 --help' for basic help or '$0 --verbose' for detailed examples"
        exit 1
        ;;
esac

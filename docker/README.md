# Langflow Docker Backend Configuration

This document provides detailed information about the Langflow backend Docker configuration, focusing on the backend-only Dockerfile, entrypoint script, and testing workflow.

## Overview

The backend Docker configuration is designed to create a production-ready container for running the Langflow backend service. It uses a multi-stage build process to optimize image size and security, and includes several best practices for containerized Python applications.

## Key Files

### 1. `build_and_push_backend_only.Dockerfile`

This Dockerfile creates a standalone backend image using a multi-stage build approach.

### 2. `backend_only_entrypoint.sh`

This script serves as the container entrypoint, configuring and starting the Langflow backend service.

### 3. `basic-test.sh`

A utility script for quickly deploying both frontend and backend containers for testing without Docker Compose.

## Dockerfile Detailed Explanation

The `build_and_push_backend_only.Dockerfile` follows a multi-stage build pattern:

### Stage 1: Builder

```dockerfile
FROM --platform=$BUILDPLATFORM ${BUILDER_BASE_IMAGE} AS builder
```

- Uses `--platform=$BUILDPLATFORM` to build on the host architecture, optimizing build performance
- Uses the `builder` image based on UV (a fast Python package installer)

#### Dependency Installation

```dockerfile
# Copy only the files needed for dependency installation
COPY ./uv.lock ./uv.lock
COPY ./README.md ./README.md
COPY ./pyproject.toml ./pyproject.toml
...

# Install the project dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    cd src/backend/base && uv sync --frozen --no-install-project --no-dev --no-editable --extra postgresql
```

- Copies only required files for dependency resolution (minimizing layer size)
- Uses a mount cache to speed up repeat builds
- Installs dependencies in a separate step before code copy, leveraging Docker's build cache
- Uses `--frozen` to ensure reproducible builds based on the lock file
- Includes PostgreSQL support as an optional extra

#### Source Installation

```dockerfile
# Copy src code into the image
COPY ./src /app/src

# Install the project's dependencies in non-editable mode
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --extra postgresql
```

- Copies the source code after dependency installation
- Installs the project in non-editable mode for production use
- Excludes development dependencies to reduce image size

### Stage 2: Runtime

```dockerfile
FROM ${PYTHON_IMAGE} AS runtime
```

- Uses a clean Python base image for the runtime environment
- Keeps the final image small by excluding build tools

#### Environment Configuration

```dockerfile
ARG DEFAULT_BACKEND_PORT=7860
ARG DEFAULT_BACKEND_HOST=0.0.0.0
ARG UID=10000
ARG GID=10000
ARG APP_USER=langflow
ARG APP_GROUP=langflow

ENV LANGFLOW_HOST=${DEFAULT_BACKEND_HOST} \
    LANGFLOW_PORT=${DEFAULT_BACKEND_PORT} \
    PATH="/app/.venv/bin:$PATH" \
    # Don't create .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    # Disable Python's buffering of stdout and stderr
    PYTHONUNBUFFERED=1 \
    ...
```

- Configures various environment variables for the application
- Uses high UID/GID (10000) to avoid conflicts with host users
- Sets Python to production mode
- Configures paths for temporary files and caching

#### System Dependencies

```dockerfile
RUN echo 'deb http://deb.debian.org/debian trixie main' > /etc/apt/sources.list.d/trixie.list \
    && echo 'APT::Default-Release "bookworm";' > /etc/apt/apt.conf.d/99defaultrelease \
    && apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends --no-install-suggests -y \
        # Process supervisor for proper signal handling
        tini=0.19.0-1 \
        git=1:2.39.5-0+deb12u2 -y \
        # PostgreSQL client libraries
        libpq5=15.12-0+deb12u2 \
        # Required for healthcheck
        curl=7.88.1-10+deb12u12 \
    # Install zlib1g from trixie for CVE-2023-45853
    && apt-get -t trixie install --no-install-recommends --no-install-suggests -y zlib1g=1:1.3.dfsg+really1.3.1-1+b1 \
    ...
```

- Installs minimal system dependencies with exact version pinning
- Uses a newer zlib1g from Debian Trixie to address CVE-2023-45853
- Includes tini as a process supervisor for proper signal handling
- Cleans up apt cache to reduce image size

#### User and Directory Setup

```dockerfile
# Create non-root user for running the application
&& groupadd --gid ${GID} ${APP_GROUP} \
&& useradd ${APP_USER} --uid ${UID} --gid ${GID} --no-create-home --home-dir /app/data \
# Create necessary directories
&& mkdir -p \
    /app/data \
    /app/cache/langflow \
    /app/flows \
    /app/db \
    /app/tmp \
# Set correct permissions
&& chown -R ${UID}:${GID} \
    /app/data \
    /app/cache \
    /app/flows \
    /app/db \
    /app/tmp \
&& chmod +x /entrypoint.sh
```

- Creates a non-root user for running the application
- Sets up directory structure for data, cache, flows, etc.
- Sets appropriate permissions for all directories

#### Health Check

```dockerfile
HEALTHCHECK --interval=30s \
    --timeout=30s \
    --start-period=20s \
    --retries=3 \
    CMD curl -f -s http://localhost:${LANGFLOW_PORT}/health | grep -q '"status":"ok"' || exit 1
```

- Configures a health check to verify the application is running properly
- Checks not just for HTTP 200 but validates actual response content
- Uses reasonable interval and timeout values

#### Security Measures

```dockerfile
# Switch to non-root user
USER ${APP_USER}
```

- Runs the container as a non-root user for security
- Uses tini as an init system to handle signals properly

#### Entrypoint Configuration

```dockerfile
# Use tini as an init system to properly handle signals and prevent zombie processes
ENTRYPOINT [ "tini", "--","/entrypoint.sh" ]

# Default command (intentionally empty to allow override at runtime)
CMD []
```

- Uses tini to handle process signals and prevent zombie processes
- Defines a flexible entrypoint that allows command line arguments

## Entrypoint Script Explanation

The `backend_only_entrypoint.sh` script handles the initialization and startup of the Langflow backend service:

### Environment Validation

```bash
#!/bin/sh
set -e

log() {
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $1"
}

# Default settings for Langflow
if [ -z "$LANGFLOW_HOST" ]; then
  log "WARNING: LANGFLOW_HOST is not set. Defaulting to 0.0.0.0"
  LANGFLOW_HOST="0.0.0.0"
fi

if [ -z "$LANGFLOW_PORT" ]; then
  log "WARNING: LANGFLOW_PORT is not set. Defaulting to 7860"
  LANGFLOW_PORT=7860
fi

# Validate port is a number
if ! echo "$LANGFLOW_PORT" | grep -q '^[0-9]\+$'; then
    log "ERROR: LANGFLOW_PORT must be a number"
    exit 1
fi
```

- Uses `set -e` to exit on any errors
- Provides a logging function with timestamps
- Sets defaults for host and port if not provided
- Validates that the port is a number

### Command Construction and Execution

```bash
# Set up logging environment
if [ -z "$LANGFLOW_LOG_ENV" ]; then
  log "Setting container logging mode"
  export LANGFLOW_LOG_ENV="container_json"
fi

# Start with the base command to run the langflow backend
CMD="python -m langflow run --backend-only --port ${LANGFLOW_PORT} --host ${LANGFLOW_HOST}"

# Add any additional arguments passed to script
if [ $# -gt 0 ]; then
  CMD="$CMD $@"
fi

log "Executing command: $CMD"

# Execute the command
exec $CMD
```

- Sets up JSON logging for container environment
- Constructs the command to start Langflow in backend-only mode
- Appends any additional arguments passed to the container
- Uses `exec` to replace the shell process with the Langflow process (important for signal handling)

## Testing with `basic-test.sh`

The `basic-test.sh` script provides a convenient way to test the Langflow stack without Docker Compose:

### Key Features

- Creates a Docker network for container communication
- Starts the backend container with proper network configuration
- Starts the frontend container configured to communicate with the backend
- Performs health checks to ensure both services are running correctly
- Provides options for monitoring and automatic cleanup

### Usage

```bash
./docker/basic-test.sh [options]

Options:
  -h, --help                 Display this help message
  -b, --backend-port PORT    Backend port (default: 7860)
  -f, --frontend-port PORT   Frontend port (default: 8080)
  --backend-image IMAGE      Backend Docker image (default: langflow_backend:latest)
  --frontend-image IMAGE     Frontend Docker image (default: langflow_frontend:latest)
  -e, --env-file FILE        Environment file path (default: .env)
  -n, --network NAME         Docker network name (default: langflow_network)
  -c, --cleanup              Cleanup containers on exit
  -m, --monitor              Keep script running to monitor containers
  --timeout SECONDS          Health check timeout in seconds (default: 30)
```

### Workflow

1. Creates a Docker network if it doesn't exist
2. Sets up and starts the backend container
3. Waits for the backend to become healthy
4. Sets up and starts the frontend container
5. Waits for the frontend to become healthy
6. Provides options for monitoring or automatic cleanup

## Building Using Makefile Commands

Langflow provides several convenient Makefile commands for building and managing Docker images:

### Building the Backend Image

```bash
# Multi-architecture build (ARM64/AMD64)
make docker_build_backend_multiarch

# ARM-specific build and load locally
make docker_build_backend_arm
```

### Quick Testing

```bash
# Run basic-test.sh to quickly deploy and test
./docker/basic-test.sh --backend-image langflow_backend:1.2.0 --frontend-image langflow_frontend:1.2.0
```

## Best Practices Implemented

The backend Docker configuration implements several best practices:

1. **Multi-stage builds** for smaller images
2. **Layer optimization** with strategic file copying
3. **Security hardening** with non-root user execution
4. **Build reproducibility** with pinned dependency versions
5. **Proper signal handling** with tini
6. **Health checks** for container orchestration
7. **Volume management** for persistent data
8. **Resource isolation** with proper directory structures
9. **Configurable runtime** with environment variables
10. **Container-optimized logging** with JSON format
11. **CVE mitigation** with updated system libraries

These practices ensure the Langflow backend container is production-ready, secure, and follows modern Docker best practices.

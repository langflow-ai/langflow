# Langflow Makefile Guide

This document provides a comprehensive explanation of the Makefile targets and their functionality in the Langflow project.

## Table of Contents

- [Overview](#overview)
- [Project Setup](#project-setup)
- [Development Workflow](#development-workflow)
- [Building](#building)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Docker Operations](#docker-operations)
- [Database Management](#database-management)
- [Load Testing](#load-testing)

## Overview

The Makefile in Langflow is designed to standardize and simplify common development tasks. It provides a consistent interface for building, testing, and running the application across different environments.

### Key Configuration Variables

```makefile
# Configurations
VERSION=$(shell grep "^version" pyproject.toml | sed 's/.*\"\(.*\)\"$$/\1/')
DOCKERFILE=docker/build_and_push.Dockerfile
DOCKERFILE_BACKEND=docker/build_and_push_backend.Dockerfile
DOCKERFILE_BACKEND_ONLY=docker/build_and_push_backend_only.Dockerfile
DOCKERFILE_FRONTEND=docker/frontend/build_and_push_frontend.Dockerfile
DOCKER_COMPOSE=docker_example/docker-compose.yml
PYTHON_REQUIRED=$(shell grep '^requires-python[[:space:]]*=' pyproject.toml | sed -n 's/.*"\([^"]*\)".*/\1/p')
PLATFORMS ?= linux/arm64,linux/amd64
BUILDER_NAME=langflow_builder
```

These variables control various aspects of the build process, including:
- Version extraction from pyproject.toml
- Docker file paths
- Target platforms for multi-architecture builds
- Docker builder configuration

## Project Setup

### Initial Setup

```bash
make init                # Initialize the project (install dependencies, build frontend)
```

The `init` target performs a complete project setup:
1. Checks for required tools (uv, npm)
2. Cleans Python and npm caches
3. Installs backend dependencies
4. Installs frontend dependencies
5. Builds the frontend static files
6. Runs the application

### Dependency Management

```bash
make install_backend     # Install backend dependencies
make install_frontend    # Install frontend dependencies
make reinstall_backend   # Force reinstall backend dependencies
make add                 # Add dependencies (use with devel=, main=, or base= parameters)
```

These targets manage project dependencies:
- `install_backend` installs Python dependencies using uv
- `install_frontend` installs npm dependencies
- `reinstall_backend` forces a clean reinstall of all dependencies
- `add` adds new dependencies to specific parts of the project

## Development Workflow

### Running the Application

```bash
make run_cli             # Run the application using CLI
make run_cli_debug       # Run the application in debug mode
make backend             # Run the backend in development mode
make frontend            # Run the frontend in development mode
```

These targets help with running the application in different modes:
- `run_cli` runs the complete application
- `run_cli_debug` runs the application with debug logging
- `backend` runs only the backend with hot reloading
- `frontend` runs only the frontend development server

### Building Frontend

```bash
make build_frontend      # Build the frontend static files
```

This target compiles the React frontend application and copies the built files to the correct location in the backend.

## Building

```bash
make build               # Build the project (frontend and backend)
make build_and_run       # Build and run the project
make build_and_install   # Build and install the project
```

These targets handle the full build process:
- `build` builds the frontend and packages the project
- `build_and_run` builds and then runs the application
- `build_and_install` builds and installs the package

## Testing

```bash
make tests               # Run all tests
make unit_tests          # Run unit tests
make integration_tests   # Run integration tests
make coverage            # Run the tests and generate a coverage report
make tests_frontend      # Run frontend tests
```

Testing targets provide different levels of test execution:
- `tests` runs all tests (unit, integration, coverage)
- `unit_tests` runs only backend unit tests
- `integration_tests` runs backend integration tests
- `coverage` generates a test coverage report
- `tests_frontend` runs frontend tests with Playwright

## Code Quality

```bash
make format              # Run code formatters
make format_backend      # Run backend code formatters
make format_frontend     # Run frontend code formatters
make lint                # Run linters
make codespell           # Run codespell to check spelling
make fix_codespell       # Run codespell to fix spelling errors
```

These targets help maintain code quality:
- `format` runs all code formatters
- `format_backend` runs ruff to format Python code
- `format_frontend` runs frontend formatters
- `lint` runs mypy for type checking
- `codespell` checks for spelling errors
- `fix_codespell` automatically fixes detected spelling errors

## Docker Operations

### Docker Image Building

```bash
make docker_build                  # Build the complete Docker image
make docker_build_backend          # Build the backend Docker image
make docker_build_frontend         # Build the frontend Docker image
make docker_buildx_setup           # Set up Docker buildx for multi-architecture builds
make docker_build_multiarch        # Build multi-architecture images
make docker_build_arm              # Build images specifically for ARM architecture
```

These targets handle Docker image creation:
- `docker_build` builds the full application image
- `docker_build_backend` and `docker_build_frontend` build separate component images
- `docker_buildx_setup` configures Docker for multi-architecture builds
- `docker_build_multiarch` builds images for multiple platforms
- `docker_build_arm` creates images optimized for ARM processors

### Docker Execution

```bash
make docker_compose_up             # Run with Docker Compose
make docker_compose_down           # Stop Docker Compose containers
make dcdev_up                      # Run development environment with Docker Compose
```

These targets manage Docker container execution:
- `docker_compose_up` starts all services with Docker Compose
- `docker_compose_down` stops and removes containers
- `dcdev_up` starts a development environment with Docker Compose

### Docker Maintenance

```bash
make docker_clean                  # Clean up Docker resources
make clear_dockerimage             # Clear dangling Docker images
```

These targets help with Docker maintenance:
- `docker_clean` removes unused containers, images, volumes, and build cache
- `clear_dockerimage` removes dangling images after builds

## Database Management

```bash
make alembic-revision              # Generate a new migration
make alembic-upgrade               # Upgrade database to the latest version
make alembic-downgrade             # Downgrade database by one version
make alembic-current               # Show current revision
make alembic-history               # Show migration history
make alembic-check                 # Check migration status
make alembic-stamp                 # Stamp the database with a specific revision
```

These targets manage database migrations using Alembic:
- `alembic-revision` creates a new migration based on model changes
- `alembic-upgrade` applies pending migrations
- `alembic-downgrade` reverts the most recent migration
- Other commands provide information and maintenance operations

## Load Testing

```bash
make locust                        # Run locust load tests
```

This target runs load testing using Locust:
- Configurable via parameters like `locust_users`, `locust_spawn_rate`, etc.
- Simulates concurrent users accessing the application
- Provides performance metrics and identifies bottlenecks

## Publishing

```bash
make publish              # Publish to PyPI
make publish_testpypi     # Publish to Test PyPI
```

These targets handle package publishing:
- `publish` builds and publishes to PyPI
- `publish_testpypi` publishes to the Test PyPI repository for validation

## Cleaning

```bash
make clean_python_cache   # Clean Python cache
make clean_npm_cache      # Clean npm cache and frontend directories
make clean_all            # Clean all caches and temporary directories
```

These targets remove temporary files:
- `clean_python_cache` removes Python compiled files and caches
- `clean_npm_cache` cleans npm caches and build directories
- `clean_all` runs all cleaning operations

## Advanced Usage

### Environment Variables

Many targets accept environment variables to customize behavior:

```bash
# Backend configuration
make backend port=8000 env=custom.env workers=4

# Frontend configuration
make run_frontend FRONTEND_START_FLAGS="--port 3001"

# Testing configuration
make unit_tests async=false lf=true ff=false
```

### Dependency Addition

```bash
# Add dev dependency to base package
make add devel="pytest-mock"

# Add main dependency
make add main="requests"

# Add dependency to base package
make add base="pydantic>=2.0"
```

### Versioning

```bash
# Increment patch version
make patch
```

## Examples

### Complete Development Setup

```bash
# Initial setup
make init

# Start development servers (in separate terminals)
make backend
make frontend

# Format code before committing
make format
```

### Running Tests

```bash
# Run unit tests with parallel execution
make unit_tests async=true

# Run specific tests
make unit_tests args="-k test_specific_function"
```

### Docker Workflow

```bash
# Build and run with Docker
make docker_build
make docker_compose_up

# Clean up Docker resources
make docker_clean
```

### Release Process

```bash
# Format and test
make format
make tests

# Build and publish
make build
make publish
```

## Utility Functions

The Makefile includes several utility functions to support operations:

- `CLEAR_DIRS` - safely clears directory contents without removing the directory
- `log_level`, `host`, `port` - common configuration parameters
- `check_tools` - validates required tools are installed
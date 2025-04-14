# Frontend NGINX Docker Tests

This directory contains tests for the NGINX frontend Docker image and the `start-nginx.sh` entry point script. The tests are designed to validate the functionality of the Docker image and script in various scenarios.

## Overview

The test suite consists of:

1. **Unit Tests for start-nginx.sh**: BATS tests that validate the script's functionality.
2. **Environment Variable Tests**: Focused tests for environment variable handling and substitution.
3. **Docker Build Tests**: Tests for validating the Dockerfile build process and image structure.
4. **Integration Tests**: End-to-end tests that validate container behavior in various scenarios.

## Requirements

- Docker
- curl
- bash 4.0+

## Getting Started

### Step 1: Setup Test Environment

First, clone the repository and navigate to the tests directory:

```bash
# Navigate to the tests directory
cd docker/frontend/tests
```

### Step 2: Review Available Tests

View available test targets:

```bash
make help
```

### Step 3: Run Tests

Run all tests:

```bash
make test
```

Or run a specific test category:

```bash
make test-shell    # Run shell script tests
make test-docker   # Run Docker build tests
make test-integration  # Run integration tests
```

## Detailed Usage

### Running Specific Tests

You can run specific test categories using the provided Makefile:

```bash
# Run only shell script tests
make test-shell

# Run only environment variable tests
make test-shell-env

# Run only Docker build tests
make test-docker

# Run only integration tests
make test-integration
```

### Running a Specific Unit Test

```bash
# List available tests
make test-shell-list

# Run a specific test
make test-shell-specific TEST_NAME="BACKEND_URL can be set via environment variable"
```

### Cleaning Up

To clean up all test artifacts:

```bash
make clean
```

Or with the main test script:

```bash
./run-all-tests.sh --clean-images
```

## Test Files

- `start-nginx-tests.bats`: Basic unit tests for the entry point script
- `env-var-tests.bats`: Environment variable handling tests
- `docker-tests.sh`: Docker image build and structure tests
- `integration-tests.sh`: Full container integration tests
- `Dockerfile.test-shell`: Docker image for testing shell scripts
- `run-all-tests.sh`: Main script to run all tests
- `Makefile`: Commands for running tests and managing test resources

## Docker-Only Testing

All tests run in Docker containers to ensure consistency across different environments. This approach:

1. Ensures all team members get identical test results regardless of local setup
2. Eliminates the need to install test dependencies locally
3. Isolates tests from the host system
4. Provides a reliable testing environment for CI/CD pipelines

## CI/CD Integration

To integrate with CI/CD systems, simply run:

```bash
./run-all-tests.sh
```

The script will return a non-zero exit code if any tests fail, which will signal a failure to CI/CD systems.

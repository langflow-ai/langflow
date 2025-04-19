.PHONY: test test-shell test-docker test-integration clean docker-test-image help test-shell-specific test-all

# Path variables - simplified for running from tests directory
SCRIPT_PATH := ../start-nginx.sh
TEMPLATE_PATH := ../default.conf.template
DOCKERFILE_PATH := ../build_and_push_frontend.Dockerfile

# Test parameters
IMAGE_NAME := langflow-frontend-test
TEST_CONTAINER_NAME := langflow-frontend-test-container
SHELL_TEST_IMAGE := langflow-shell-test

# Default target when running 'make' without arguments
.DEFAULT_GOAL := help

# Help target
help: ## Display this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Frontend NGINX Testing Targets:"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Main test target
test: test-shell test-docker test-integration ## Run all tests (shell, docker, and integration)

# Clean up test artifacts
clean: ## Clean up all test artifacts and containers
	@echo "Cleaning up test artifacts..."
	@docker stop $(TEST_CONTAINER_NAME) 2>/dev/null || true
	@docker rm $(TEST_CONTAINER_NAME) 2>/dev/null || true
	@docker rmi $(IMAGE_NAME) 2>/dev/null || true
	@docker rmi $(SHELL_TEST_IMAGE) 2>/dev/null || true
	@find . -type d -name "tmp.*" -exec rm -rf {} + 2>/dev/null || true

# Build Docker test image
docker-test-image: ## Build Docker image for shell script testing
	@echo "Building Docker test image for shell script tests..."
	@docker build -t $(SHELL_TEST_IMAGE) -f Dockerfile.test-shell .

# Run shell script tests in Docker
test-shell: docker-test-image ## Run shell script tests in Docker container
	@echo "Running shell script tests in Docker container..."
	@if [ ! -f "$(SCRIPT_PATH)" ]; then \
		echo "Error: Script file '$(SCRIPT_PATH)' not found!"; \
		exit 1; \
	fi
	@if [ ! -f "$(TEMPLATE_PATH)" ]; then \
		echo "Error: Template file '$(TEMPLATE_PATH)' not found!"; \
		exit 1; \
	fi
	@docker run --rm \
		-v "$(shell pwd)/$(SCRIPT_PATH):/start-nginx.sh:ro" \
		-v "$(shell pwd)/$(TEMPLATE_PATH):/etc/nginx/conf.d/default.conf.template:ro" \
		-v "$(shell pwd)/start-nginx-tests.bats:/tests/start-nginx-tests.bats:ro" \
		-e SCRIPT_PATH=/start-nginx.sh \
		-e CONFIG_TEMPLATE_PATH=/etc/nginx/conf.d/default.conf.template \
		-e TESTS_PATH=/tests/start-nginx-tests.bats \
		$(SHELL_TEST_IMAGE)

# Run environment variable tests in Docker
test-shell-env: docker-test-image ## Run environment variable tests in Docker container
	@echo "Running shell script environment variable tests in Docker container..."
	@if [ ! -f "$(SCRIPT_PATH)" ]; then \
		echo "Error: Script file '$(SCRIPT_PATH)' not found!"; \
		exit 1; \
	fi
	@if [ ! -f "$(TEMPLATE_PATH)" ]; then \
		echo "Error: Template file '$(TEMPLATE_PATH)' not found!"; \
		exit 1; \
	fi
	@docker run --rm \
		-v "$(shell pwd)/$(SCRIPT_PATH):/start-nginx.sh:ro" \
		-v "$(shell pwd)/$(TEMPLATE_PATH):/etc/nginx/conf.d/default.conf.template:ro" \
		-v "$(shell pwd)/env-var-tests.bats:/tests/start-nginx-tests.bats:ro" \
		-e SCRIPT_PATH=/start-nginx.sh \
		-e CONFIG_TEMPLATE_PATH=/etc/nginx/conf.d/default.conf.template \
		-e TESTS_PATH=/tests/start-nginx-tests.bats \
		$(SHELL_TEST_IMAGE)

# Run Docker build and structure tests
test-docker: ## Run Docker build and structure tests
	@echo "Running Docker build and structure tests..."
	@chmod +x docker-tests.sh
	@./docker-tests.sh

# Run Integration tests
test-integration: ## Run integration tests for runtime behavior
	@echo "Running integration tests..."
	@chmod +x integration-tests.sh
	@./integration-tests.sh

# List available shell script tests
test-shell-list: ## List available shell script tests
	@echo "Available shell script tests:"
	@echo ""
	@echo "From start-nginx-tests.bats:"
	@grep -e "^@test" start-nginx-tests.bats | sed 's/@test "//' | sed 's/" {//'
	@echo ""
	@if [ -f "env-var-tests.bats" ]; then \
		echo "From env-var-tests.bats:"; \
		grep -e "^@test" env-var-tests.bats | sed 's/@test "//' | sed 's/" {//'; \
		echo ""; \
	fi
	@echo "Run individual test with: make test-shell-specific TEST_NAME='test_name'"

# Run specific shell script test
test-shell-specific: docker-test-image ## Run a specific shell script test (usage: make test-shell-specific TEST_NAME='test_name')
	@if [ -z "$(TEST_NAME)" ]; then \
		echo "Error: TEST_NAME parameter is required. Use: make test-shell-specific TEST_NAME='test_name'"; \
		exit 1; \
	fi
	@if [ ! -f "$(SCRIPT_PATH)" ]; then \
		echo "Error: Script file '$(SCRIPT_PATH)' not found!"; \
		exit 1; \
	fi
	@if [ ! -f "$(TEMPLATE_PATH)" ]; then \
		echo "Error: Template file '$(TEMPLATE_PATH)' not found!"; \
		exit 1; \
	fi
	@docker run --rm \
		-v "$(shell pwd)/$(SCRIPT_PATH):/start-nginx.sh:ro" \
		-v "$(shell pwd)/$(TEMPLATE_PATH):/etc/nginx/conf.d/default.conf.template:ro" \
		-v "$(shell pwd)/start-nginx-tests.bats:/tests/start-nginx-tests.bats:ro" \
		-e SCRIPT_PATH=/start-nginx.sh \
		-e CONFIG_TEMPLATE_PATH=/etc/nginx/conf.d/default.conf.template \
		-e TESTS_PATH=/tests/start-nginx-tests.bats \
		$(SHELL_TEST_IMAGE) -f "$(TEST_NAME)"

# Run all tests with comprehensive test runner
test-all: ## Run all tests with comprehensive output and reporting
	@echo "Running comprehensive test suite..."
	@chmod +x run-all-tests.sh
	@./run-all-tests.sh

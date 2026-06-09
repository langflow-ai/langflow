.PHONY: all help init install dev format lint test build build_wheel build_sdist publish publish_test clean

# Configurations
VERSION=$(shell grep "^version" pyproject.toml | sed 's/.*\"\(.*\)\"$$/\1/')
GREEN=\033[0;32m
NC=\033[0m # No Color

all: help

help: ## show this help message
	@echo '----'
	@grep -hE '^\S+:.*##' $(MAKEFILE_LIST) | \
	awk -F ':.*##' '{printf "\033[36mmake %s\033[0m: %s\n", $$1, $$2}' | \
	column -c2 -t -s :
	@echo '----'

init: ## initialize the project
	@echo "$(GREEN)Installing SDK dependencies...$(NC)"
	@uv sync --dev
	@echo "$(GREEN)SDK project initialized.$(NC)"

install: ## install the project dependencies
	@echo "$(GREEN)Installing SDK dependencies...$(NC)"
	@uv sync

dev: ## install development dependencies
	@echo "$(GREEN)Installing SDK development dependencies...$(NC)"
	@uv sync --dev

format: dev ## format the code
	@echo "$(GREEN)Formatting SDK code...$(NC)"
	@uv run ruff check . --fix
	@uv run ruff format .

lint: dev ## run linters
	@echo "$(GREEN)Running SDK linters...$(NC)"
	@uv run ruff check .

test: dev ## run tests
	@echo "$(GREEN)Running SDK tests...$(NC)"
	@uv run pytest tests -v $(args)

build: ## build the project
	@echo "$(GREEN)Building SDK...$(NC)"
	@rm -rf dist/
	@uv build --out-dir dist $(args)
	@echo "$(GREEN)SDK build completed. Artifacts in dist/$(NC)"

build_wheel: ## build wheel only
	@make build args="--wheel"

build_sdist: ## build source distribution only
	@make build args="--sdist"

publish: ## publish to PyPI
	@echo "$(GREEN)Publishing SDK to PyPI...$(NC)"
	@uv publish

publish_test: ## publish to test PyPI
	@echo "$(GREEN)Publishing SDK to test PyPI...$(NC)"
	@uv publish --repository testpypi

clean: ## clean build artifacts
	@echo "$(GREEN)Cleaning SDK build artifacts...$(NC)"
	@rm -rf dist/
	@find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name '*.pyc' -delete
	@echo "$(GREEN)Cleanup completed.$(NC)"

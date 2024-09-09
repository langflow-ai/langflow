.PHONY: all init format lint build build_frontend install_frontend run_frontend run_backend dev help tests coverage clean_python_cache clean_npm_cache clean_all

# Configurations
VERSION=$(shell grep "^version" pyproject.toml | sed 's/.*\"\(.*\)\"$$/\1/')
DOCKERFILE=docker/build_and_push.Dockerfile
DOCKERFILE_BACKEND=docker/build_and_push_backend.Dockerfile
DOCKERFILE_FRONTEND=docker/frontend/build_and_push_frontend.Dockerfile
DOCKER_COMPOSE=docker_example/docker-compose.yml
PYTHON_REQUIRED=$(shell grep '^python[[:space:]]*=' pyproject.toml | sed -n 's/.*"\([^"]*\)".*/\1/p')
RED=\033[0;31m
NC=\033[0m # No Color
GREEN=\033[0;32m

log_level ?= debug
host ?= 0.0.0.0
port ?= 7860
env ?= .env
open_browser ?= true
path = src/backend/base/langflow/frontend
workers ?= 1
async ?= true
all: help

######################
# UTILITIES
######################

# increment the patch version of the current package
patch: ## bump the version in langflow and langflow-base
	@echo 'Patching the version'
	@poetry version patch
	@echo 'Patching the version in langflow-base'
	@cd src/backend/base && poetry version patch
	@make lock

# check for required tools
check_tools:
	@command -v poetry >/dev/null 2>&1 || { echo >&2 "$(RED)Poetry is not installed. Aborting.$(NC)"; exit 1; }
	@command -v npm >/dev/null 2>&1 || { echo >&2 "$(RED)NPM is not installed. Aborting.$(NC)"; exit 1; }
	@command -v docker >/dev/null 2>&1 || { echo >&2 "$(RED)Docker is not installed. Aborting.$(NC)"; exit 1; }
	@command -v pipx >/dev/null 2>&1 || { echo >&2 "$(RED)pipx is not installed. Aborting.$(NC)"; exit 1; }
	@$(MAKE) check_env
	@echo "$(GREEN)All required tools are installed.$(NC)"

# check if Python version is compatible
check_env: ## check if Python version is compatible
	@chmod +x scripts/setup/check_env.sh
	@PYTHON_INSTALLED=$$(scripts/setup/check_env.sh python --version 2>&1 | awk '{print $$2}'); \
	if ! scripts/setup/check_env.sh python -c "import sys; from packaging.specifiers import SpecifierSet; from packaging.version import Version; sys.exit(not SpecifierSet('$(PYTHON_REQUIRED)').contains(Version('$$PYTHON_INSTALLED')))" 2>/dev/null; then \
		echo "$(RED)Error: Python version $$PYTHON_INSTALLED is not compatible with the required version $(PYTHON_REQUIRED). Aborting.$(NC)"; exit 1; \
	fi

help: ## show this help message
	@echo '----'
	@grep -hE '^\S+:.*##' $(MAKEFILE_LIST) | \
	awk -F ':.*##' '{printf "\033[36mmake %s\033[0m: %s\n", $$1, $$2}' | \
	column -c2 -t -s :
	@echo '----'

######################
# INSTALL PROJECT
######################

install_backend: ## install the backend dependencies
	@echo 'Installing backend dependencies'
	@poetry install > /dev/null 2>&1

install_frontend: ## install the frontend dependencies
	@echo 'Installing frontend dependencies'
	@cd src/frontend && npm install > /dev/null 2>&1

build_frontend: ## build the frontend static files
	@echo 'Building frontend static files'
	@cd src/frontend && CI='' npm run build > /dev/null 2>&1
	@rm -rf src/backend/base/langflow/frontend
	@cp -r src/frontend/build src/backend/base/langflow/frontend

init: check_tools clean_python_cache clean_npm_cache ## initialize the project
	@make install_backend
	@make install_frontend
	@make build_frontend
	@echo "$(GREEN)All requirements are installed.$(NC)"
	@python -m langflow run

######################
# CLEAN PROJECT
######################

clean_python_cache:
	@echo "Cleaning Python cache..."
	find . -type d -name '__pycache__' -exec rm -r {} +
	find . -type f -name '*.py[cod]' -exec rm -f {} +
	find . -type f -name '*~' -exec rm -f {} +
	find . -type f -name '.*~' -exec rm -f {} +
	find . -type d -empty -delete
	@echo "$(GREEN)Python cache cleaned.$(NC)"

clean_npm_cache:
	@echo "Cleaning npm cache..."
	cd src/frontend && npm cache clean --force
	rm -rf src/frontend/node_modules src/frontend/build src/backend/base/langflow/frontend src/frontend/package-lock.json
	@echo "$(GREEN)NPM cache and frontend directories cleaned.$(NC)"

clean_all: clean_python_cache clean_npm_cache # clean all caches and temporary directories
	@echo "$(GREEN)All caches and temporary directories cleaned.$(NC)"

setup_poetry: ## install poetry using pipx
	pipx install poetry

add:
	@echo 'Adding dependencies'
ifdef devel
	@cd src/backend/base && poetry add --group dev $(devel)
endif

ifdef main
	@poetry add $(main)
endif

ifdef base
	@cd src/backend/base && poetry add $(base)
endif



######################
# CODE TESTS
######################

coverage: ## run the tests and generate a coverage report
	@poetry run coverage run
	@poetry run coverage erase

unit_tests: ## run unit tests
ifeq ($(async), true)
	poetry run pytest src/backend/tests \
		--ignore=src/backend/tests/integration \
		--instafail -n auto -ra -m "not api_key_required" \
		--durations-path src/backend/tests/.test_durations \
		--splitting-algorithm least_duration \
		$(args)
else
	poetry run pytest src/backend/tests \
		--ignore=src/backend/tests/integration \
		--instafail -ra -m "not api_key_required" \
		--durations-path src/backend/tests/.test_durations \
		--splitting-algorithm least_duration \
		$(args)
endif

unit_tests_looponfail:
	@make unit_tests args="-f"

integration_tests:
	poetry run pytest src/backend/tests/integration \
		--instafail -ra \
		$(args)

integration_tests_no_api_keys:
	poetry run pytest src/backend/tests/integration \
		--instafail -ra -m "not api_key_required" \
		$(args)

integration_tests_api_keys:
	poetry run pytest src/backend/tests/integration \
		--instafail -ra -m "api_key_required" \
		$(args)

tests: ## run unit, integration, coverage tests
	@echo 'Running Unit Tests...'
	make unit_tests
	@echo 'Running Integration Tests...'
	make integration_tests
	@echo 'Running Coverage Tests...'
	make coverage

######################
# CODE QUALITY
######################

codespell: ## run codespell to check spelling
	@poetry install --with spelling
	poetry run codespell --toml pyproject.toml

fix_codespell: ## run codespell to fix spelling errors
	@poetry install --with spelling
	poetry run codespell --toml pyproject.toml --write

format: ## run code formatters
	@poetry run ruff check . --fix
	@poetry run ruff format .
	@cd src/frontend && npm run format

lint: install_backend ## run linters
	@poetry run mypy --namespace-packages -p "langflow"

install_frontendci:
	@cd src/frontend && npm ci > /dev/null 2>&1

install_frontendc:
	@cd src/frontend && rm -rf node_modules package-lock.json && npm install > /dev/null 2>&1

run_frontend: ## run the frontend
	@-kill -9 `lsof -t -i:3000`
	@cd src/frontend && npm start

tests_frontend: ## run frontend tests
ifeq ($(UI), true)
	@cd src/frontend && npx playwright test --ui --project=chromium
else
	@cd src/frontend && npx playwright test --project=chromium
endif

run_cli: install_frontend install_backend build_frontend ## run the CLI
	@echo 'Running the CLI'
ifdef env
	@make start env=$(env) host=$(host) port=$(port) log_level=$(log_level)
else
	@make start host=$(host) port=$(port) log_level=$(log_level)
endif

run_cli_debug:
	@echo 'Running the CLI in debug mode'
	@make install_frontend > /dev/null
	@echo 'Building the frontend'
	@make build_frontend > /dev/null
	@echo 'Install backend dependencies'
	@make install_backend > /dev/null
ifdef env
	@make start env=$(env) host=$(host) port=$(port) log_level=debug
else
	@make start host=$(host) port=$(port) log_level=debug
endif

start:
	@echo 'Running the CLI'

ifeq ($(open_browser),false)
	@make install_backend && poetry run langflow run \
		--path $(path) \
		--log-level $(log_level) \
		--host $(host) \
		--port $(port) \
		--env-file $(env) \
		--no-open-browser
else
	@make install_backend && poetry run langflow run \
		--path $(path) \
		--log-level $(log_level) \
		--host $(host) \
		--port $(port) \
		--env-file $(env)
endif

setup_devcontainer: ## set up the development container
	make install_backend
	make install_frontend
	make build_frontend
	poetry run langflow --path src/frontend/build

setup_env: ## set up the environment
	@sh ./scripts/setup/setup_env.sh

frontend: install_frontend ## run the frontend in development mode
	make run_frontend

frontendc: install_frontendc
	make run_frontend


backend: setup_env install_backend ## run the backend in development mode
	@-kill -9 $$(lsof -t -i:7860) || true
ifdef login
	@echo "Running backend autologin is $(login)";
	LANGFLOW_AUTO_LOGIN=$(login) poetry run uvicorn \
		--factory langflow.main:create_app \
		--host 0.0.0.0 \
		--port $(port) \
		$(if $(filter-out 1,$(workers)),, --reload) \
		--env-file $(env) \
		--loop asyncio \
		$(if $(workers),--workers $(workers),)
else
	@echo "Running backend respecting the $(env) file";
	poetry run uvicorn \
		--factory langflow.main:create_app \
		--host 0.0.0.0 \
		--port $(port) \
		$(if $(filter-out 1,$(workers)),, --reload) \
		--env-file $(env) \
		--loop asyncio \
		$(if $(workers),--workers $(workers),)
endif

build_and_run: setup_env ## build the project and run it
	rm -rf dist
	rm -rf src/backend/base/dist
	make build
	poetry run pip install dist/*.tar.gz
	poetry run langflow run

build_and_install: ## build the project and install it
	@echo 'Removing dist folder'
	rm -rf dist
	rm -rf src/backend/base/dist
	make build && poetry run pip install dist/*.whl && pip install src/backend/base/dist/*.whl --force-reinstall

build: setup_env ## build the frontend static files and package the project
ifdef base
	make install_frontendci
	make build_frontend
	make build_langflow_base
endif

ifdef main
	make install_frontendci
	make build_frontend
	make build_langflow_base
	make build_langflow
endif

build_langflow_base:
	cd src/backend/base && poetry build
	rm -rf src/backend/base/langflow/frontend

build_langflow_backup:
	poetry lock && poetry build

build_langflow:
	cd ./scripts && poetry run python update_dependencies.py
	poetry lock --no-update
	poetry build
ifdef restore
	mv pyproject.toml.bak pyproject.toml
	mv poetry.lock.bak poetry.lock
endif

dev: ## run the project in development mode with docker compose
	make install_frontend
ifeq ($(build),1)
	@echo 'Running docker compose up with build'
	docker compose $(if $(debug),-f docker-compose.debug.yml) up --build
else
	@echo 'Running docker compose up without build'
	docker compose $(if $(debug),-f docker-compose.debug.yml) up
endif

docker_build: dockerfile_build clear_dockerimage ## build DockerFile

docker_build_backend: dockerfile_build_be clear_dockerimage ## build Backend DockerFile

docker_build_frontend: dockerfile_build_fe clear_dockerimage ## build Frontend Dockerfile

dockerfile_build:
	@echo 'BUILDING DOCKER IMAGE: ${DOCKERFILE}'
	@docker build --rm \
		-f ${DOCKERFILE} \
		-t langflow:${VERSION} .

dockerfile_build_be: dockerfile_build
	@echo 'BUILDING DOCKER IMAGE BACKEND: ${DOCKERFILE_BACKEND}'
	@docker build --rm \
		--build-arg LANGFLOW_IMAGE=langflow:${VERSION} \
		-f ${DOCKERFILE_BACKEND} \
		-t langflow_backend:${VERSION} .

dockerfile_build_fe: dockerfile_build
	@echo 'BUILDING DOCKER IMAGE FRONTEND: ${DOCKERFILE_FRONTEND}'
	@docker build --rm \
		--build-arg LANGFLOW_IMAGE=langflow:${VERSION} \
		-f ${DOCKERFILE_FRONTEND} \
		-t langflow_frontend:${VERSION} .

clear_dockerimage:
	@echo 'Clearing the docker build'
	@if docker images -f "dangling=true" -q | grep -q '.*'; then \
		docker rmi $$(docker images -f "dangling=true" -q); \
	fi

docker_compose_up: docker_build docker_compose_down
	@echo 'Running docker compose up'
	docker compose -f $(DOCKER_COMPOSE) up --remove-orphans

docker_compose_down:
	@echo 'Running docker compose down'
	docker compose -f $(DOCKER_COMPOSE) down || true

dcdev_up:
	@echo 'Running docker compose up'
	docker compose -f docker/dev.docker-compose.yml down || true
	docker compose -f docker/dev.docker-compose.yml up --remove-orphans

lock_base:
	cd src/backend/base && poetry lock

lock_langflow:
	poetry lock

lock: ## lock dependencies
	@echo 'Locking dependencies'
	cd src/backend/base && poetry lock --no-update
	poetry lock --no-update

update: ## update dependencies
	@echo 'Updating dependencies'
	cd src/backend/base && poetry update
	poetry update

publish_base:
	cd src/backend/base && poetry publish --skip-existing

publish_langflow:
	poetry publish

publish_base_testpypi:
	cd src/backend/base && poetry publish --skip-existing -r test-pypi

publish_langflow_testpypi:
	poetry publish -r test-pypi

publish: ## build the frontend static files and package the project and publish it to PyPI
	@echo 'Publishing the project'
ifdef base
	make publish_base
endif

ifdef main
	make publish_langflow
endif

publish_testpypi: ## build the frontend static files and package the project and publish it to PyPI
	@echo 'Publishing the project'

ifdef base
	poetry config repositories.test-pypi https://test.pypi.org/legacy/
	make publish_base_testpypi
endif

ifdef main
	poetry config repositories.test-pypi https://test.pypi.org/legacy/
	make publish_langflow_testpypi
endif


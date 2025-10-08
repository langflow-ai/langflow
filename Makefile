.PHONY: all init format_backend format lint build run_backend dev help tests coverage clean_python_cache clean_npm_cache clean_frontend_build clean_all run_clic load_test_setup load_test_setup_basic load_test_list_flows load_test_run load_test_langflow_quick load_test_stress load_test_example load_test_clean load_test_remote_setup load_test_remote_run load_test_help

# Configurations
VERSION=$(shell grep "^version" pyproject.toml | sed 's/.*\"\(.*\)\"$$/\1/')
DOCKER=podman
DOCKERFILE=docker/build_and_push.Dockerfile
DOCKERFILE_BACKEND=docker/build_and_push_backend.Dockerfile
DOCKERFILE_FRONTEND=docker/frontend/build_and_push_frontend.Dockerfile
DOCKER_COMPOSE=docker_example/docker-compose.yml
PYTHON_REQUIRED=$(shell grep '^requires-python[[:space:]]*=' pyproject.toml | sed -n 's/.*"\([^"]*\)".*/\1/p')
RED=\033[0;31m
NC=\033[0m # No Color
GREEN=\033[0;32m
YELLOW=\033[1;33m

log_level ?= debug
host ?= 0.0.0.0
port ?= 7860
env ?= .env
open_browser ?= true
path = src/backend/base/langflow/frontend
workers ?= 1
async ?= true
lf ?= false
ff ?= true
all: help

######################
# UTILITIES
######################

# Some directories may be mount points as in devcontainer, so we need to clear their
# contents rather than remove the entire directory. But we must also be mindful that
# we are not running in a devcontainer, so need to ensure the directories exist.
# See https://code.visualstudio.com/remote/advancedcontainers/improve-performance
CLEAR_DIRS = $(foreach dir,$1,$(shell mkdir -p $(dir) && find $(dir) -mindepth 1 -delete))

# check for required tools
check_tools:
	@command -v uv >/dev/null 2>&1 || { echo >&2 "$(RED)uv is not installed. Aborting.$(NC)"; exit 1; }
	@command -v npm >/dev/null 2>&1 || { echo >&2 "$(RED)NPM is not installed. Aborting.$(NC)"; exit 1; }
	@echo "$(GREEN)All required tools are installed.$(NC)"

help: ## show this help message
	@echo '----'
	@grep -hE '^\S+:.*##' $(MAKEFILE_LIST) | \
	awk -F ':.*##' '{printf "\033[36mmake %s\033[0m: %s\n", $$1, $$2}' | \
	column -c2 -t -s :
	@echo '----'
	@echo 'For frontend commands, run: make help_frontend'

######################
# INSTALL PROJECT
######################

reinstall_backend: ## forces reinstall all dependencies (no caching)
	@echo 'Installing backend dependencies'
	@uv sync -n --reinstall --frozen

install_backend: ## install the backend dependencies
	@echo 'Installing backend dependencies'
	@uv sync --frozen --extra "postgresql" $(EXTRA_ARGS)



init: check_tools ## initialize the project
	@make install_backend
	@make install_frontend
	@uvx pre-commit install
	@echo "$(GREEN)All requirements are installed.$(NC)"

######################
# CLEAN PROJECT
######################

clean_python_cache:
	@echo "Cleaning Python cache..."
	find . -type d -name '__pycache__' -exec rm -r {} +
	find . -type f -name '*.py[cod]' -exec rm -f {} +
	find . -type f -name '*~' -exec rm -f {} +
	find . -type f -name '.*~' -exec rm -f {} +
	$(call CLEAR_DIRS,.mypy_cache )
	@echo "$(GREEN)Python cache cleaned.$(NC)"

clean_npm_cache:
	@echo "Cleaning npm cache..."
	cd src/frontend && npm cache clean --force
	$(call CLEAR_DIRS,src/frontend/node_modules src/frontend/build src/backend/base/langflow/frontend)
	rm -f src/frontend/package-lock.json
	@echo "$(GREEN)NPM cache and frontend directories cleaned.$(NC)"

clean_frontend_build: ## clean frontend build artifacts to ensure fresh build
	@echo "Cleaning frontend build artifacts..."
	@echo "  - Removing src/frontend/build directory"
	$(call CLEAR_DIRS,src/frontend/build)
	@echo "  - Removing built frontend files from backend"
	$(call CLEAR_DIRS,src/backend/base/langflow/frontend)
	@echo "$(GREEN)Frontend build artifacts cleaned - fresh build guaranteed.$(NC)"

clean_all: clean_python_cache clean_npm_cache # clean all caches and temporary directories
	@echo "$(GREEN)All caches and temporary directories cleaned.$(NC)"

setup_uv: ## install uv using pipx
	pipx install uv

add:
	@echo 'Adding dependencies'
ifdef devel
	@cd src/backend/base && uv add --group dev $(devel)
endif

ifdef main
	@uv add $(main)
endif

ifdef base
	@cd src/backend/base && uv add $(base)
endif



######################
# CODE TESTS
######################

coverage: ## run the tests and generate a coverage report
	@uv run coverage run
	@uv run coverage erase

unit_tests: ## run unit tests
	@uv sync --frozen
	@EXTRA_ARGS=""
	@if [ "$(async)" = "true" ]; then \
		EXTRA_ARGS="$$EXTRA_ARGS --instafail -n auto"; \
	fi; \
	if [ "$(lf)" = "true" ]; then \
		EXTRA_ARGS="$$EXTRA_ARGS --lf"; \
	fi; \
	if [ "$(ff)" = "true" ]; then \
		EXTRA_ARGS="$$EXTRA_ARGS --ff"; \
	fi; \
	uv run pytest src/backend/tests/unit \
	--ignore=src/backend/tests/integration \
	--ignore=src/backend/tests/unit/template \
	$$EXTRA_ARGS \
	--instafail -ra -m 'not api_key_required' \
	--durations-path src/backend/tests/.test_durations \
	--splitting-algorithm least_duration $(args)

unit_tests_looponfail:
	@make unit_tests args="-f"

lfx_tests: ## run lfx package unit tests
	@echo 'Running LFX Package Tests...'
	@cd src/lfx && \
	uv sync && \
	uv run pytest tests/unit -v $(args)

integration_tests:
	uv run pytest src/backend/tests/integration \
		--instafail -ra \
		$(args)

integration_tests_no_api_keys:
	uv run pytest src/backend/tests/integration \
		--instafail -ra -m "not api_key_required" \
		$(args)

integration_tests_api_keys:
	uv run pytest src/backend/tests/integration \
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
# TEMPLATE TESTING
######################

template_tests: ## run all starter project template tests
	@echo 'Running Starter Project Template Tests...'
	@uv run pytest src/backend/tests/unit/template/test_starter_projects.py -v -n auto

######################
# CODE QUALITY
######################

codespell: ## run codespell to check spelling
	@uvx codespell --toml pyproject.toml

fix_codespell: ## run codespell to fix spelling errors
	@uvx codespell --toml pyproject.toml --write

format_backend: ## backend code formatters
	@uv run ruff check . --fix
	@uv run ruff format .

format: format_backend format_frontend ## run code formatters

format_frontend_check: ## run biome check without formatting
	@echo 'Running Biome check on frontend...'
	@cd src/frontend && npx @biomejs/biome check

unsafe_fix:
	@uv run ruff check . --fix --unsafe-fixes

lint: install_backend ## run linters
	@uv run mypy --namespace-packages -p "langflow"



run_clic: clean_frontend_build install_frontend install_backend build_frontend ## run the CLI with fresh frontend build
	@echo 'Running the CLI with fresh frontend build'
	@uv run langflow run \
		--frontend-path $(path) \
		--log-level $(log_level) \
		--host $(host) \
		--port $(port) \
		$(if $(env),--env-file $(env),) \
		$(if $(filter false,$(open_browser)),--no-open-browser)

run_cli: install_frontend install_backend build_frontend ## run the CLI quickly (without cleaning build cache)
	@echo 'Running the CLI quickly (reusing existing build cache if available)'
	@uv run langflow run \
		--frontend-path $(path) \
		--log-level $(log_level) \
		--host $(host) \
		--port $(port) \
		$(if $(env),--env-file $(env),) \
		$(if $(filter false,$(open_browser)),--no-open-browser)

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


setup_devcontainer: ## set up the development container
	make install_backend
	make install_frontend
	make build_frontend
	uv run langflow --frontend-path src/frontend/build

setup_env: ## set up the environment
	@sh ./scripts/setup/setup_env.sh




backend: setup_env install_backend ## run the backend in development mode
	@-kill -9 $$(lsof -t -i:7860) || true
ifdef login
	@echo "Running backend autologin is $(login)";
	LANGFLOW_AUTO_LOGIN=$(login) uv run uvicorn \
		--factory langflow.main:create_app \
		--host 0.0.0.0 \
		--port $(port) \
		$(if $(filter-out 1,$(workers)),, --reload) \
		--env-file $(env) \
		--loop asyncio \
		$(if $(workers),--workers $(workers),)
else
	@echo "Running backend respecting the $(env) file";
	uv run uvicorn \
		--factory langflow.main:create_app \
		--host 0.0.0.0 \
		--port $(port) \
		$(if $(filter-out 1,$(workers)),, --reload) \
		--env-file $(env) \
		--loop asyncio \
		$(if $(workers),--workers $(workers),)
endif

build_and_run: setup_env ## build the project and run it
	$(call CLEAR_DIRS,dist src/backend/base/dist)
	make build
	uv run pip install dist/*.tar.gz
	uv run langflow run

build_and_install: ## build the project and install it
	@echo 'Removing dist folder'
	$(call CLEAR_DIRS,dist src/backend/base/dist)
	make build && uv run pip install dist/*.whl && pip install src/backend/base/dist/*.whl --force-reinstall

build: setup_env ## build the frontend static files and package the project
ifdef base
	make install_frontendci
	make build_frontend
	make build_langflow_base args="$(args)"
endif

ifdef main
	make install_frontendci
	make build_frontend
	make build_langflow_base args="$(args)"
	make build_langflow args="$(args)"
endif

build_langflow_base:
	cd src/backend/base && uv build $(args)

build_langflow_backup:
	uv lock && uv build

build_langflow:
	uv lock --no-upgrade
	uv build $(args)
ifdef restore
	mv pyproject.toml.bak pyproject.toml
	mv uv.lock.bak uv.lock
endif


docker_build: dockerfile_build clear_dockerimage ## build DockerFile

docker_build_backend: dockerfile_build_be clear_dockerimage ## build Backend DockerFile

docker_build_frontend: dockerfile_build_fe clear_dockerimage ## build Frontend Dockerfile

dockerfile_build:
	@echo 'BUILDING DOCKER IMAGE: ${DOCKERFILE}'
	@command -v $(DOCKER) >/dev/null 2>&1 || { echo "Error: $(DOCKER) is not installed. Please install $(DOCKER), or run 'make docker_build DOCKER=podman' (or DOCKER=docker) if you have an alternative installed."; exit 1; }
	@$(DOCKER) build --rm \
		-f ${DOCKERFILE} \
		-t langflow:${VERSION} .

dockerfile_build_be: dockerfile_build
	@echo 'BUILDING DOCKER IMAGE BACKEND: ${DOCKERFILE_BACKEND}'
	@command -v $(DOCKER) >/dev/null 2>&1 || { echo "Error: $(DOCKER) is not installed. Please install $(DOCKER), or run 'make docker_build_backend DOCKER=podman' (or DOCKER=docker) if you have an alternative installed."; exit 1; }
	@$(DOCKER) build --rm \
		--build-arg LANGFLOW_IMAGE=langflow:${VERSION} \
		-f ${DOCKERFILE_BACKEND} \
		-t langflow_backend:${VERSION} .

dockerfile_build_fe: dockerfile_build
	@echo 'BUILDING DOCKER IMAGE FRONTEND: ${DOCKERFILE_FRONTEND}'
	@command -v $(DOCKER) >/dev/null 2>&1 || { echo "Error: $(DOCKER) is not installed. Please install $(DOCKER), or run 'make docker_build_frontend DOCKER=podman' (or DOCKER=docker) if you have an alternative installed."; exit 1; }
	@$(DOCKER) build --rm \
		--build-arg LANGFLOW_IMAGE=langflow:${VERSION} \
		-f ${DOCKERFILE_FRONTEND} \
		-t langflow_frontend:${VERSION} .

clear_dockerimage:
	@echo 'Clearing the docker build'
	@if $(DOCKER) images -f "dangling=true" -q | grep -q '.*'; then \
		$(DOCKER) rmi $$($(DOCKER) images -f "dangling=true" -q); \
	fi

docker_compose_up: docker_build docker_compose_down
	@echo 'Running docker compose up'
	$(DOCKER) compose -f $(DOCKER_COMPOSE) up --remove-orphans

docker_compose_down:
	@echo 'Running docker compose down'
	$(DOCKER) compose -f $(DOCKER_COMPOSE) down || true

dcdev_up:
	@echo 'Running docker compose up'
	$(DOCKER) compose -f docker/dev.docker-compose.yml down || true
	$(DOCKER) compose -f docker/dev.docker-compose.yml up --remove-orphans

lock_base:
	cd src/backend/base && uv lock

lock_langflow:
	uv lock

lock: ## lock dependencies
	@echo 'Locking dependencies'
	cd src/backend/base && uv lock
	uv lock

update: ## update dependencies
	@echo 'Updating dependencies'
	cd src/backend/base && uv sync --upgrade
	uv sync --upgrade

publish_base:
	cd src/backend/base && uv publish

publish_langflow:
	uv publish

publish_base_testpypi:
	# TODO: update this to use the test-pypi repository
	cd src/backend/base && uv publish -r test-pypi

publish_langflow_testpypi:
	# TODO: update this to use the test-pypi repository
	uv publish -r test-pypi

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

######################
# LFX PACKAGE
######################

lfx_build: ## build the LFX package
	@echo 'Building LFX package'
	@cd src/lfx && make build

lfx_publish: ## publish LFX package to PyPI
	@echo 'Publishing LFX package'
	@cd src/lfx && make publish

lfx_publish_testpypi: ## publish LFX package to test PyPI
	@echo 'Publishing LFX package to test PyPI'
	@cd src/lfx && make publish_test

lfx_test: ## run LFX tests
	@echo 'Running LFX tests'
	@cd src/lfx && make test

lfx_format: ## format LFX code
	@echo 'Formatting LFX code'
	@cd src/lfx && make format

lfx_lint: ## lint LFX code
	@echo 'Linting LFX code'
	@cd src/lfx && make lint

lfx_clean: ## clean LFX build artifacts
	@echo 'Cleaning LFX build artifacts'
	@cd src/lfx && make clean

lfx_docker_build: ## build LFX production Docker image
	@echo 'Building LFX Docker image'
	@cd src/lfx && make docker_build

lfx_docker_dev: ## start LFX development environment
	@echo 'Starting LFX development environment'
	@cd src/lfx && make docker_dev

lfx_docker_test: ## run LFX tests in Docker
	@echo 'Running LFX tests in Docker'
	@cd src/lfx && make docker_test

# example make alembic-revision message="Add user table"
alembic-revision: ## generate a new migration
	@echo 'Generating a new Alembic revision'
	cd src/backend/base/langflow/ && uv run alembic revision --autogenerate -m "$(message)"


alembic-upgrade: ## upgrade database to the latest version
	@echo 'Upgrading database to the latest version'
	cd src/backend/base/langflow/ && uv run alembic upgrade head

alembic-downgrade: ## downgrade database by one version
	@echo 'Downgrading database by one version'
	cd src/backend/base/langflow/ && uv run alembic downgrade -1

alembic-current: ## show current revision
	@echo 'Showing current Alembic revision'
	cd src/backend/base/langflow/ && uv run alembic current

alembic-history: ## show migration history
	@echo 'Showing Alembic migration history'
	cd src/backend/base/langflow/ && uv run alembic history --verbose

alembic-check: ## check migration status
	@echo 'Running alembic check'
	cd src/backend/base/langflow/ && uv run alembic check

alembic-stamp: ## stamp the database with a specific revision
	@echo 'Stamping the database with revision $(revision)'
	cd src/backend/base/langflow/ && uv run alembic stamp $(revision)

######################
# VERSION MANAGEMENT
######################

patch: ## Update version across all projects. Usage: make patch v=1.5.0
	@if [ -z "$(v)" ]; then \
		echo "$(RED)Error: Version argument required.$(NC)"; \
		echo "Usage: make patch v=1.5.0"; \
		exit 1; \
	fi; \
	echo "$(GREEN)Updating version to $(v)$(NC)"; \
	\
	LANGFLOW_VERSION="$(v)"; \
	LANGFLOW_BASE_VERSION=$$(echo "$$LANGFLOW_VERSION" | sed -E 's/^[0-9]+\.(.*)$$/0.\1/'); \
	\
	echo "$(GREEN)Langflow version: $$LANGFLOW_VERSION$(NC)"; \
	echo "$(GREEN)Langflow-base version: $$LANGFLOW_BASE_VERSION$(NC)"; \
	\
	echo "$(GREEN)Updating main pyproject.toml...$(NC)"; \
	python -c "import re; fname='pyproject.toml'; txt=open(fname).read(); txt=re.sub(r'^version = \".*\"', 'version = \"$$LANGFLOW_VERSION\"', txt, flags=re.MULTILINE); txt=re.sub(r'\"langflow-base==.*\"', '\"langflow-base==$$LANGFLOW_BASE_VERSION\"', txt); open(fname, 'w').write(txt)"; \
	\
	echo "$(GREEN)Updating langflow-base pyproject.toml...$(NC)"; \
	python -c "import re; fname='src/backend/base/pyproject.toml'; txt=open(fname).read(); txt=re.sub(r'^version = \".*\"', 'version = \"$$LANGFLOW_BASE_VERSION\"', txt, flags=re.MULTILINE); open(fname, 'w').write(txt)"; \
	\
	echo "$(GREEN)Updating frontend package.json...$(NC)"; \
	python -c "import re; fname='src/frontend/package.json'; txt=open(fname).read(); txt=re.sub(r'\"version\": \".*\"', '\"version\": \"$$LANGFLOW_VERSION\"', txt); open(fname, 'w').write(txt)"; \
	\
	echo "$(GREEN)Validating version changes...$(NC)"; \
	if ! grep -q "^version = \"$$LANGFLOW_VERSION\"" pyproject.toml; then echo "$(RED)✗ Main pyproject.toml version validation failed$(NC)"; exit 1; fi; \
	if ! grep -q "\"langflow-base==$$LANGFLOW_BASE_VERSION\"" pyproject.toml; then echo "$(RED)✗ Main pyproject.toml langflow-base dependency validation failed$(NC)"; exit 1; fi; \
	if ! grep -q "^version = \"$$LANGFLOW_BASE_VERSION\"" src/backend/base/pyproject.toml; then echo "$(RED)✗ Langflow-base pyproject.toml version validation failed$(NC)"; exit 1; fi; \
	if ! grep -q "\"version\": \"$$LANGFLOW_VERSION\"" src/frontend/package.json; then echo "$(RED)✗ Frontend package.json version validation failed$(NC)"; exit 1; fi; \
	echo "$(GREEN)✓ All versions updated successfully$(NC)"; \
	\
	echo "$(GREEN)Syncing dependencies in parallel...$(NC)"; \
	uv sync --quiet & \
	(cd src/frontend && npm install --silent) & \
	wait; \
	\
	echo "$(GREEN)Validating final state...$(NC)"; \
	CHANGED_FILES=$$(git status --porcelain | wc -l | tr -d ' '); \
	if [ "$$CHANGED_FILES" -lt 5 ]; then \
		echo "$(RED)✗ Expected at least 5 changed files, but found $$CHANGED_FILES$(NC)"; \
		echo "$(RED)Changed files:$(NC)"; \
		git status --porcelain; \
		exit 1; \
	fi; \
	EXPECTED_FILES="pyproject.toml uv.lock src/backend/base/pyproject.toml src/frontend/package.json src/frontend/package-lock.json"; \
	for file in $$EXPECTED_FILES; do \
		if ! git status --porcelain | grep -q "$$file"; then \
			echo "$(RED)✗ Expected file $$file was not modified$(NC)"; \
			exit 1; \
		fi; \
	done; \
	echo "$(GREEN)✓ All required files were modified.$(NC)"; \
	\
	echo "$(GREEN)Version update complete!$(NC)"; \
	echo "$(GREEN)Updated files:$(NC)"; \
	echo "  - pyproject.toml: $$LANGFLOW_VERSION"; \
	echo "  - src/backend/base/pyproject.toml: $$LANGFLOW_BASE_VERSION"; \
	echo "  - src/frontend/package.json: $$LANGFLOW_VERSION"; \
	echo "  - uv.lock: dependency lock updated"; \
	echo "  - src/frontend/package-lock.json: dependency lock updated"; \
	echo "$(GREEN)Dependencies synced successfully!$(NC)"

######################
# LOAD TESTING
######################

# Default values for locust configuration
locust_users ?= 10
locust_spawn_rate ?= 1
locust_host ?= http://localhost:7860
locust_headless ?= true
locust_time ?= 300s
locust_api_key ?= your-api-key
locust_flow_id ?= your-flow-id
locust_file ?= src/backend/tests/locust/locustfile.py
locust_min_wait ?= 2000
locust_max_wait ?= 5000
locust_request_timeout ?= 30.0

locust: ## run locust load tests (options: locust_users=10 locust_spawn_rate=1 locust_host=http://localhost:7860 locust_headless=true locust_time=300s locust_api_key=your-api-key locust_flow_id=your-flow-id locust_file=src/backend/tests/locust/locustfile.py locust_min_wait=2000 locust_max_wait=5000 locust_request_timeout=30.0)
	@if [ ! -f "$(locust_file)" ]; then \
		echo "$(RED)Error: Locustfile not found at $(locust_file)$(NC)"; \
		exit 1; \
	fi
	@echo "Starting Locust with $(locust_users) users, spawn rate of $(locust_spawn_rate)"
	@echo "Testing host: $(locust_host)"
	@echo "Using locustfile: $(locust_file)"
	@export API_KEY=$(locust_api_key) && \
	export FLOW_ID=$(locust_flow_id) && \
	export LANGFLOW_HOST=$(locust_host) && \
	export MIN_WAIT=$(locust_min_wait) && \
	export MAX_WAIT=$(locust_max_wait) && \
	export REQUEST_TIMEOUT=$(locust_request_timeout) && \
	cd $$(dirname "$(locust_file)") && \
	if [ "$(locust_headless)" = "true" ]; then \
		uv run locust \
			--headless \
			-u $(locust_users) \
			-r $(locust_spawn_rate) \
			--run-time $(locust_time) \
			--host $(locust_host) \
			-f $$(basename "$(locust_file)"); \
	else \
		uv run locust \
			-u $(locust_users) \
			-r $(locust_spawn_rate) \
			--host $(locust_host) \
			-f $$(basename "$(locust_file)"); \
	fi

# Enhanced load testing targets with improved error handling and shapes
load_test_host ?= http://127.0.0.1:8000
load_test_flow_id ?= 5523731d-5ef3-56de-b4ef-59b0a224fdbc
load_test_api_key ?= test
html ?= false

load_test_ramp100: ## Run 100-user ramp load test (3min, 0->100 users @ 5/s). Options: html=true, load_test_host, load_test_flow_id, load_test_api_key
	@echo "$(YELLOW)Running 100-user ramp load test (3 minutes)$(NC)"
	@export FLOW_ID=$(load_test_flow_id) && \
	export API_KEY=$(load_test_api_key) && \
	export REQUEST_TIMEOUT=10 && \
	cd src/backend/tests/locust && \
	if [ "$(html)" = "true" ]; then \
		echo "$(GREEN)Generating HTML report: ramp100_test.html$(NC)"; \
		uv run locust -f locustfile_complex_serve.py --host $(load_test_host) --headless --html ramp100_test.html; \
	else \
		uv run locust -f locustfile_complex_serve.py --host $(load_test_host) --headless; \
	fi

load_test_cliff: ## Find performance cliff with step ramp (5->50 users, 30s steps). Options: html=true, load_test_host, load_test_flow_id, load_test_api_key
	@echo "$(YELLOW)Running step ramp to find performance cliff$(NC)"
	@export FLOW_ID=$(load_test_flow_id) && \
	export API_KEY=$(load_test_api_key) && \
	export REQUEST_TIMEOUT=10 && \
	cd src/backend/tests/locust && \
	if [ "$(html)" = "true" ]; then \
		echo "$(GREEN)Generating HTML report: cliff_test.html$(NC)"; \
		uv run locust -f lfx_step_ramp.py --host $(load_test_host) --headless --html cliff_test.html; \
	else \
		uv run locust -f lfx_step_ramp.py --host $(load_test_host) --headless; \
	fi

load_test_lfx_quick: ## Quick LFX load test (30 users, 60s). Options: html=true, load_test_host, load_test_flow_id, load_test_api_key
	@echo "$(YELLOW)Running quick 30-user load test (60 seconds)$(NC)"
	@export FLOW_ID=$(load_test_flow_id) && \
	export API_KEY=$(load_test_api_key) && \
	export REQUEST_TIMEOUT=10 && \
	cd src/backend/tests/locust && \
	if [ "$(html)" = "true" ]; then \
		echo "$(GREEN)Generating HTML report: quick_test.html$(NC)"; \
		uv run locust -f lfx_serve_locustfile.py --host $(load_test_host) --headless -u 30 -r 5 -t 60s --html quick_test.html; \
	else \
		uv run locust -f lfx_serve_locustfile.py --host $(load_test_host) --headless -u 30 -r 5 -t 60s; \
	fi

######################
# ENHANCED LOAD TESTING
######################

# Enhanced load testing system with API-based flow loading
load_test_setup: ## Set up load test environment with starter project flows
	@echo "$(YELLOW)Setting up Langflow load test environment$(NC)"
	@cd src/backend/tests/locust && uv run python langflow_setup_test.py --interactive

load_test_setup_basic: ## Set up load test environment with Basic Prompting flow
	@echo "$(YELLOW)Setting up load test environment with Basic Prompting flow$(NC)"
	@cd src/backend/tests/locust && uv run python langflow_setup_test.py --flow "Basic Prompting" --save-credentials load_test_creds.json

load_test_list_flows: ## List available starter project flows
	@echo "$(YELLOW)Listing available starter project flows$(NC)"
	@cd src/backend/tests/locust && uv run python langflow_setup_test.py --list-flows

load_test_run: ## Run load test (automatically sets up if needed). Use FLOW_NAME="Flow Name" to specify flow
	@echo "$(YELLOW)Running load test with enhanced error logging$(NC)"
	@if [ ! -f "src/backend/tests/locust/load_test_creds.json" ]; then \
		echo "$(BLUE)No credentials found. Running automatic setup...$(NC)"; \
		if [ -z "$(FLOW_NAME)" ]; then \
			echo "$(CYAN)Available flows:$(NC)"; \
			cd src/backend/tests/locust && uv run python langflow_setup_test.py --list-flows; \
			echo "$(RED)Please specify a flow: make load_test_run FLOW_NAME=\"Basic Prompting\"$(NC)"; \
			exit 1; \
		else \
			echo "$(BLUE)Setting up with flow: $(FLOW_NAME)$(NC)"; \
			cd src/backend/tests/locust && uv run python langflow_setup_test.py --flow "$(FLOW_NAME)" --save-credentials load_test_creds.json; \
		fi \
	fi
	@cd src/backend/tests/locust && \
	export API_KEY=$$(python -c "import json; print(json.load(open('load_test_creds.json'))['api_key'])") && \
	export FLOW_ID=$$(python -c "import json; print(json.load(open('load_test_creds.json'))['flow_id'])") && \
	uv run python langflow_run_load_test.py --headless --users 20 --duration 120 --no-start-langflow --html load_test_report.html --csv load_test_results

load_test_langflow_quick: ## Quick Langflow load test (10 users, 30s) with HTML report (automatically sets up if needed). Use FLOW_NAME="Flow Name" to specify flow
	@echo "$(YELLOW)Running quick Langflow load test with HTML report$(NC)"
	@if [ ! -f "src/backend/tests/locust/load_test_creds.json" ]; then \
		echo "$(BLUE)No credentials found. Running automatic setup...$(NC)"; \
		if [ -z "$(FLOW_NAME)" ]; then \
			echo "$(CYAN)Available flows:$(NC)"; \
			cd src/backend/tests/locust && uv run python langflow_setup_test.py --list-flows; \
			echo "$(RED)Please specify a flow: make load_test_langflow_quick FLOW_NAME=\"Basic Prompting\"$(NC)"; \
			exit 1; \
		else \
			echo "$(BLUE)Setting up with flow: $(FLOW_NAME)$(NC)"; \
			cd src/backend/tests/locust && uv run python langflow_setup_test.py --flow "$(FLOW_NAME)" --save-credentials load_test_creds.json; \
		fi \
	fi
	@cd src/backend/tests/locust && \
	export API_KEY=$$(python -c "import json; print(json.load(open('load_test_creds.json'))['api_key'])") && \
	export FLOW_ID=$$(python -c "import json; print(json.load(open('load_test_creds.json'))['flow_id'])") && \
	uv run python langflow_run_load_test.py --headless --users 10 --duration 30 --no-start-langflow --html quick_test_report.html

load_test_stress: ## Stress test (100 users, 5 minutes) with comprehensive reporting (automatically sets up if needed). Use FLOW_NAME="Flow Name" to specify flow
	@echo "$(YELLOW)Running stress test with comprehensive reporting$(NC)"
	@if [ ! -f "src/backend/tests/locust/load_test_creds.json" ]; then \
		echo "$(BLUE)No credentials found. Running automatic setup...$(NC)"; \
		if [ -z "$(FLOW_NAME)" ]; then \
			echo "$(CYAN)Available flows:$(NC)"; \
			cd src/backend/tests/locust && uv run python langflow_setup_test.py --list-flows; \
			echo "$(RED)Please specify a flow: make load_test_stress FLOW_NAME=\"Basic Prompting\"$(NC)"; \
			exit 1; \
		else \
			echo "$(BLUE)Setting up with flow: $(FLOW_NAME)$(NC)"; \
			cd src/backend/tests/locust && uv run python langflow_setup_test.py --flow "$(FLOW_NAME)" --save-credentials load_test_creds.json; \
		fi \
	fi
	@cd src/backend/tests/locust && \
	export API_KEY=$$(python -c "import json; print(json.load(open('load_test_creds.json'))['api_key'])") && \
	export FLOW_ID=$$(python -c "import json; print(json.load(open('load_test_creds.json'))['flow_id'])") && \
	uv run python langflow_run_load_test.py --headless --users 100 --spawn-rate 5 --duration 300 --no-start-langflow --html stress_test_report.html --csv stress_test_results --shape ramp100

load_test_example: ## Run complete example workflow (setup + test + reports)
	@echo "$(YELLOW)Running complete load test example workflow$(NC)"
	@cd src/backend/tests/locust && uv run python langflow_example_workflow.py --auto

load_test_clean: ## Clean up load test files and credentials
	@echo "$(YELLOW)Cleaning up load test files$(NC)"
	@cd src/backend/tests/locust && rm -f *.json *.html *.csv *.log
	@echo "$(GREEN)Load test files cleaned$(NC)"

load_test_remote_setup: ## Set up load test for remote instance (requires LANGFLOW_HOST)
	@if [ -z "$(LANGFLOW_HOST)" ]; then \
		echo "$(RED)Error: LANGFLOW_HOST environment variable required$(NC)"; \
		echo "$(YELLOW)Example: export LANGFLOW_HOST=https://your-remote-instance.com$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Setting up load test for remote instance: $(LANGFLOW_HOST)$(NC)"
	@cd src/backend/tests/locust && uv run python langflow_setup_test.py --host $(LANGFLOW_HOST) --flow "Basic Prompting" --save-credentials remote_test_creds.json

load_test_remote_run: ## Run load test against remote instance (requires prior setup)
	@if [ -z "$(LANGFLOW_HOST)" ]; then \
		echo "$(RED)Error: LANGFLOW_HOST environment variable required$(NC)"; \
		exit 1; \
	fi
	@if [ ! -f "src/backend/tests/locust/remote_test_creds.json" ]; then \
		echo "$(RED)Error: No remote credentials found. Run 'make load_test_remote_setup' first$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Running load test against remote instance: $(LANGFLOW_HOST)$(NC)"
	@cd src/backend/tests/locust && \
	export API_KEY=$$(python -c "import json; print(json.load(open('remote_test_creds.json'))['api_key'])") && \
	export FLOW_ID=$$(python -c "import json; print(json.load(open('remote_test_creds.json'))['flow_id'])") && \
	uv run python langflow_run_load_test.py --host $(LANGFLOW_HOST) --no-start-langflow --headless --users 10 --spawn-rate 1 --duration 120 --html remote_test_report.html

load_test_help: ## Show detailed load testing help
	@echo "$(GREEN)Langflow Enhanced Load Testing System$(NC)"
	@echo ""
	@echo "$(YELLOW)Quick Start (Local):$(NC)"
	@echo "  1. make load_test_setup_basic    # Set up with Basic Prompting flow"
	@echo "  2. make load_test_langflow_quick # Run quick Langflow test"
	@echo "  3. Open quick_test_report.html  # View results"
	@echo ""
	@echo "$(YELLOW)Remote Testing:$(NC)"
	@echo "  1. export LANGFLOW_HOST=https://your-instance.com"
	@echo "  2. make load_test_remote_setup   # Set up for remote testing"
	@echo "  3. make load_test_remote_run     # Run test against remote instance"
	@echo ""
	@echo "$(YELLOW)Available Commands:$(NC)"
	@echo "  load_test_setup        - Interactive flow selection setup"
	@echo "  load_test_setup_basic  - Quick setup with Basic Prompting"
	@echo "  load_test_list_flows   - List available starter flows"
	@echo "  load_test_run          - Standard load test (25 users, 2 min)"
	@echo "  load_test_langflow_quick - Quick Langflow test (10 users, 30s)"
	@echo "  load_test_quick        - Quick complex serve test (30 users, 60s)"
	@echo "  load_test_stress       - Stress test (100 users, 5 min)"
	@echo "  load_test_example      - Complete example workflow"
	@echo "  load_test_clean        - Clean up generated files"
	@echo ""
	@echo "$(YELLOW)Generated Reports:$(NC)"
	@echo "  - *.html files         - Interactive HTML reports"
	@echo "  - *_results_*.csv      - Raw performance data"
	@echo "  - *_detailed_errors_*.log - Comprehensive error logs"
	@echo "  - *_error_summary_*.json  - Error analysis"

######################
# INCLUDE FRONTEND MAKEFILE
######################

# Include frontend-specific Makefile
include Makefile.frontend

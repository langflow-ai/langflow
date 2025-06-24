.PHONY: all init format_backend format_frontend format lint build build_frontend install_frontend run_frontend run_backend dev help tests coverage clean_python_cache clean_npm_cache clean_all

# Configurations
VERSION=$(shell grep "^version" pyproject.toml | sed 's/.*\"\(.*\)\"$$/\1/')
DOCKERFILE=docker/build_and_push.Dockerfile
DOCKERFILE_BACKEND=docker/build_and_push_backend.Dockerfile
DOCKERFILE_FRONTEND=docker/frontend/build_and_push_frontend.Dockerfile
DOCKER_COMPOSE=docker_example/docker-compose.yml
PYTHON_REQUIRED=$(shell grep '^requires-python[[:space:]]*=' pyproject.toml | sed -n 's/.*"\([^"]*\)".*/\1/p')
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

######################
# INSTALL PROJECT
######################

reinstall_backend: ## forces reinstall all dependencies (no caching)
	@echo 'Installing backend dependencies'
	@uv sync -n --reinstall --frozen

install_backend: ## install the backend dependencies
	@echo 'Installing backend dependencies'
	@uv sync --frozen --extra "postgresql" $(EXTRA_ARGS)

install_frontend: ## install the frontend dependencies
	@echo 'Installing frontend dependencies'
	@cd src/frontend && npm install > /dev/null 2>&1

build_frontend: ## build the frontend static files
	@echo '==== Starting frontend build ===='
	@echo 'Current directory: $$(pwd)'
	@echo 'Checking if src/frontend exists...'
	@ls -la src/frontend || true
	@echo 'Building frontend static files...'
	@cd src/frontend && CI='' npm run build 2>&1 || { echo "\nBuild failed! Error output above ☝️"; exit 1; }
	@echo 'Clearing destination directory...'
	$(call CLEAR_DIRS,src/backend/base/langflow/frontend)
	@echo 'Copying build files...'
	@cp -r src/frontend/build/. src/backend/base/langflow/frontend
	@echo '==== Frontend build complete ===='

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
	--ignore=src/backend/tests/integration $$EXTRA_ARGS \
	--instafail -ra -m 'not api_key_required' \
	--durations-path src/backend/tests/.test_durations \
	--splitting-algorithm least_duration $(args)

unit_tests_looponfail:
	@make unit_tests args="-f"

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
# CODE QUALITY
######################

codespell: ## run codespell to check spelling
	@uvx codespell --toml pyproject.toml

fix_codespell: ## run codespell to fix spelling errors
	@uvx codespell --toml pyproject.toml --write

format_backend: ## backend code formatters
	@uv run ruff check . --fix
	@uv run ruff format . --config pyproject.toml

format_frontend: ## frontend code formatters
	@cd src/frontend && npm run format

format: format_backend format_frontend ## run code formatters

unsafe_fix:
	@uv run ruff check . --fix --unsafe-fixes

lint: install_backend ## run linters
	@uv run mypy --namespace-packages -p "langflow"

install_frontendci:
	@cd src/frontend && npm ci > /dev/null 2>&1

install_frontendc:
	@cd src/frontend && $(call CLEAR_DIRS,node_modules) && rm -f package-lock.json && npm install > /dev/null 2>&1

run_frontend: ## run the frontend
	@-kill -9 `lsof -t -i:3000`
	@cd src/frontend && npm start $(if $(FRONTEND_START_FLAGS),-- $(FRONTEND_START_FLAGS))

tests_frontend: ## run frontend tests
ifeq ($(UI), true)
	@cd src/frontend && npx playwright test --ui --project=chromium
else
	@cd src/frontend && npx playwright test --project=chromium
endif

run_cli: install_frontend install_backend build_frontend ## run the CLI
	@echo 'Running the CLI'
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

frontend: install_frontend ## run the frontend in development mode
	make run_frontend

frontendc: install_frontendc
	make run_frontend


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
	echo "$(GREEN)Syncing backend dependencies...$(NC)"; \
	uv sync --frozen; \
	\
	echo "$(GREEN)Installing frontend dependencies...$(NC)"; \
	(cd src/frontend && npm install); \
	\
	echo "$(GREEN)Version update complete!$(NC)"; \
	echo "$(GREEN)Updated files:$(NC)"; \
	echo "  - pyproject.toml: $$LANGFLOW_VERSION"; \
	echo "  - src/backend/base/pyproject.toml: $$LANGFLOW_BASE_VERSION"; \
	echo "  - src/frontend/package.json: $$LANGFLOW_VERSION"; \
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

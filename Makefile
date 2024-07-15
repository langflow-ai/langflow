.PHONY: all init format lint build build_frontend install_frontend run_frontend run_backend dev help tests coverage clean_python_cache clean_npm_cache clean_all

# Configurations
VERSION=$(shell grep "^version" pyproject.toml | sed 's/.*\"\(.*\)\"$$/\1/')
DOCKERFILE=docker/build_and_push.Dockerfile
DOCKERFILE_BACKEND=docker/build_and_push_backend.Dockerfile
DOCKERFILE_FRONTEND=docker/frontend/build_and_push_frontend.Dockerfile
DOCKER_COMPOSE=docker_example/docker-compose.yml

log_level ?= debug
host ?= 0.0.0.0
port ?= 7860
env ?= .env
open_browser ?= true
path = src/backend/base/langflow/frontend
workers ?= 1

all: help

clean_python_cache:
	@echo 'Cleaning Python cache...'
	find . -type d -name '__pycache__' -exec rm -r {} +
	find . -type f -name '*.py[cod]' -exec rm -f {} +
	find . -type f -name '*~' -exec rm -f {} +
	find . -type f -name '.*~' -exec rm -f {} +
	@echo 'Python cache cleaned.'

clean_npm_cache:
	@echo 'Cleaning npm cache...'
	cd src/frontend && npm cache clean --force
	rm -rf src/frontend/node_modules
	rm -f src/frontend/package-lock.json
	@echo 'NPM cache cleaned.'

clean_all: clean_python_cache clean_npm_cache
	@echo 'All caches cleaned.'

codespell:
	@poetry install --with spelling
	poetry run codespell --toml pyproject.toml

fix_codespell:
	@poetry install --with spelling
	poetry run codespell --toml pyproject.toml --write

setup_poetry:
	pipx install poetry

add:
	@echo 'Adding dependencies'
ifdef devel
	cd src/backend/base && poetry add --group dev $(devel)
endif

ifdef main
	poetry add $(main)
endif

ifdef base
	cd src/backend/base && poetry add $(base)
endif

init: check_tools ## initialize the project
	@echo 'Installing backend dependencies'
	make install_backend
	@echo 'Installing frontend dependencies'
	make install_frontend

coverage: ## run the tests and generate a coverage report
	@poetry run coverage run
	@poetry run coverage erase

# allow passing arguments to pytest
unit_tests:
	poetry run pytest \
		--ignore=tests/integration \
		--instafail -ra -n auto -m "not api_key_required" \
		$(args)

integration_tests:
	poetry run pytest tests/integration \
		--instafail -ra -n auto \
		$(args)

format: ## run code formatters
	poetry run ruff check . --fix
	poetry run ruff format .
	cd src/frontend && npm run format

lint: ## run linters
	poetry run mypy --namespace-packages -p "langflow"

install_frontend: ## install the frontend dependencies
	cd src/frontend && npm install

install_frontendci:
	cd src/frontend && npm ci

install_frontendc:
	cd src/frontend && rm -rf node_modules package-lock.json && npm install

run_frontend:
	@-kill -9 `lsof -t -i:3000`
	cd src/frontend && npm start

tests_frontend:
ifeq ($(UI), true)
	cd src/frontend && npx playwright test --ui --project=chromium
else
	cd src/frontend && npx playwright test --project=chromium
endif

run_cli:
	@echo 'Running the CLI'
	@make install_frontend > /dev/null
	@echo 'Install backend dependencies'
	@make install_backend > /dev/null
	@echo 'Building the frontend'
	@make build_frontend > /dev/null
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

setup_devcontainer:
	make init
	make build_frontend
	poetry run langflow --path src/frontend/build

setup_env:
	@sh ./scripts/setup/update_poetry.sh 1.8.2
	@sh ./scripts/setup/setup_env.sh

frontend: ## run the frontend in development mode
	make install_frontend
	make run_frontend

frontendc:
	make install_frontendc
	make run_frontend

install_backend:
	@echo 'Installing backend dependencies'
	@poetry install
	@poetry run pre-commit install

backend: ## run the backend in development mode
	@echo 'Setting up the environment'
	@make setup_env
	make install_backend
	@-kill -9 $$(lsof -t -i:7860)
ifdef login
	@echo "Running backend autologin is $(login)";
	LANGFLOW_AUTO_LOGIN=$(login) poetry run uvicorn \
		--factory langflow.main:create_app \
		--host 0.0.0.0 \
		--port $(port) \
		--reload \
		--env-file $(env) \
		--loop asyncio \
		--workers $(workers)
else
	@echo "Running backend respecting the $(env) file";
	poetry run uvicorn \
		--factory langflow.main:create_app \
		--host 0.0.0.0 \
		--port $(port) \
		--reload \
		--env-file $(env) \
		--loop asyncio \
		--workers $(workers)
endif

build_and_run:
	@echo 'Removing dist folder'
	@make setup_env
	rm -rf dist
	rm -rf src/backend/base/dist
	make build
	poetry run pip install dist/*.tar.gz
	poetry run langflow run

build_and_install:
	@echo 'Removing dist folder'
	rm -rf dist
	rm -rf src/backend/base/dist
	make build && poetry run pip install dist/*.whl && pip install src/backend/base/dist/*.whl --force-reinstall

build_frontend: ## build the frontend static files
	cd src/frontend && CI='' npm run build
	rm -rf src/backend/base/langflow/frontend
	cp -r src/frontend/build src/backend/base/langflow/frontend

build: ## build the frontend static files and package the project
	@echo 'Building the project'
	@make setup_env
ifdef base
	make install_frontendci
	make build_frontend
	make build_langflow_base
endif

ifdef main
	make build_langflow
endif

build_langflow_base:
	cd src/backend/base && poetry build
	rm -rf src/backend/base/langflow/frontend

build_langflow_backup:
	poetry lock && poetry build

build_langflow:
	cd ./scripts && poetry run python update_dependencies.py
	poetry lock
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

lock_base:
	cd src/backend/base && poetry lock

lock_langflow:
	poetry lock

lock:
# Run both in parallel
	@echo 'Locking dependencies'
	cd src/backend/base && poetry lock
	poetry lock

update:
	@echo 'Updating dependencies'
	cd src/backend/base && poetry update
	poetry update

publish_base:
	cd src/backend/base && poetry publish

publish_langflow:
	poetry publish

publish: ## build the frontend static files and package the project and publish it to PyPI
	@echo 'Publishing the project'
ifdef base
	make publish_base
endif

ifdef main
	make publish_langflow
endif

check_tools: ## check for required tools
	@command -v poetry >/dev/null 2>&1 || { echo >&2 "Poetry is not installed. Aborting."; exit 1; }
	@command -v npm >/dev/null 2>&1 || { echo >&2 "NPM is not installed. Aborting."; exit 1; }
	@command -v docker >/dev/null 2>&1 || { echo >&2 "Docker is not installed. Aborting."; exit 1; }
	@command -v pipx >/dev/null 2>&1 || { echo >&2 "pipx is not installed. Aborting."; exit 1; }
	@echo "All required tools are installed."

help: ## show this help message
	@echo '----'
	@grep -hE '^\S+:.*##' $(MAKEFILE_LIST) | \
	awk -F ':.*##' '{printf "\033[36mmake %s\033[0m: %s\n", $$1, $$2}' | \
	column -c2 -t -s :
	@echo '----'

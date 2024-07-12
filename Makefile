.PHONY: all init format lint build build_frontend install_frontend run_frontend run_backend dev help tests coverage

all: help
log_level ?= debug
host ?= 0.0.0.0
port ?= 7860
env ?= .env
open_browser ?= true
path = src/backend/base/langflow/frontend
workers ?= 1


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


init:
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


help: ## show this help message
	@echo '----'
	@echo -e "$$(grep -hE '^\S+:.*##' $(MAKEFILE_LIST) | \
	sed -e 's/:.*##\s*/:/' \
	-e 's/^\(.\+\):\(.*\)/\\x1b[36mmake \1\\x1b[m:\2/' | \
	column -c2 -t -s :']]')"
	@echo '----'

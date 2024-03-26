.PHONY: all init format lint build build_frontend install_frontend run_frontend run_backend dev help tests coverage

all: help

setup_poetry:
	pipx install poetry
	poetry self add poetry-monorepo-dependency-plugin

init:
	@echo 'Installing backend dependencies'
	make install_backend
	@echo 'Installing frontend dependencies'
	make install_frontend

coverage:
	poetry run pytest --cov \
		--cov-config=.coveragerc \
		--cov-report xml \
		--cov-report term-missing:skip-covered

# allow passing arguments to pytest
tests:
	@make install_backend

	poetry run pytest tests --instafail $(args)
# Use like:

format:
	poetry run ruff . --fix
	poetry run ruff format .
	cd src/frontend && npm run format

lint:
	make install_backend
	poetry run mypy src/backend
	poetry run ruff . --fix

install_frontend:
	cd src/frontend && npm install

install_frontendc:
	cd src/frontend && rm -rf node_modules package-lock.json && npm install

run_frontend:
	@-kill -9 `lsof -t -i:3000`
	cd src/frontend && npm start

tests_frontend:
ifeq ($(UI), true)
		cd src/frontend && ./run-tests.sh --ui
else
		cd src/frontend && ./run-tests.sh
endif

run_cli:
	@echo 'Running the CLI'
	@make install_frontend > /dev/null
	@echo 'Building the frontend'
	@make build_frontend > /dev/null
	@echo 'Install backend dependencies'
	@make install_backend > /dev/null
	ifdef env
		poetry run langflow run --path src/frontend/build --host $(host) --port $(port) --env-file $(env)
	else
		poetry run langflow run --path src/frontend/build --host $(host) --port $(port) --env-file .env
	endif

run_cli_debug:
	@echo 'Running the CLI in debug mode'
	@make install_frontend > /dev/null
	@echo 'Building the frontend'
	@make build_frontend > /dev/null
	@echo 'Install backend dependencies'
	@make install_backend > /dev/null
	ifdef env
		poetry run langflow run --path src/frontend/build --log-level debug --host $(host) --port $(port) --env-file $(env)
	else
		poetry run langflow run --path src/frontend/build --log-level debug --host $(host) --port $(port) --env-file .env
	endif

setup_devcontainer:
	make init
	make build_frontend
	poetry run langflow --path src/frontend/build

setup_env:
	@sh ./scripts/setup/update_poetry.sh 1.8.2
	@sh ./scripts/setup/setup_env.sh

frontend:
	make install_frontend
	make run_frontend

frontendc:
	make install_frontendc
	make run_frontend

install_backend:
	@echo 'Installing backend dependencies'
	@make setup_env
	@poetry install --extras deploy

backend:
	make install_backend
	@-kill -9 `lsof -t -i:7860`
ifeq ($(login),1)
	@echo "Running backend without autologin";
	poetry run uvicorn --factory langflow.main:create_app --host 0.0.0.0 --port 7860 --reload --env-file .env
else
	@echo "Running backend with autologin";
	LANGFLOW_AUTO_LOGIN=True poetry run uvicorn --factory langflow.main:create_app --host 0.0.0.0 --port 7860 --reload --env-file .env
endif

build_and_run:
	@echo 'Removing dist folder'
	rm -rf dist
	rm -rf src/backend/base/dist
	make build
	poetry run pip install dist/*.tar.gz && pip install src/backend/base/dist/*.tar.gz
	poetry run langflow run

build_and_install:
	@echo 'Removing dist folder'
	rm -rf dist
	rm -rf src/backend/base/dist
	make build && poetry run pip install dist/*.whl && pip install src/backend/base/dist/*.whl --force-reinstall

build_frontend:
	cd src/frontend && CI='' npm run build
	cp -r src/frontend/build src/backend/base/langflow/frontend

build:
	@echo 'Building the project'
	@make setup_env
	make build_langflow_base
	make build_langflow

build_langflow:
	poetry build-rewrite-path-deps --version-pinning-strategy=semver

build_langflow_base:
	make install_frontend
	make build_frontend
	cd src/backend/base && poetry build-rewrite-path-deps --version-pinning-strategy=semver
	rm -rf src/backend/base/langflow/frontend

dev:
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
	# cd src/backend/base && poetry lock
	# poetry lock
	@echo 'Locking dependencies'
	@make -j2 lock_base lock_langflow
publish_base:
	make build_langflow_base
	cd src/backend/base && poetry publish

publish_langflow:
	make build_langflow
	poetry publish

publish:
	make publish_base
	make publish_langflow

help:
	@echo '----'
	@echo 'format              - run code formatters'
	@echo 'lint                - run linters'
	@echo 'install_frontend    - install the frontend dependencies'
	@echo 'build_frontend      - build the frontend static files'
	@echo 'run_frontend        - run the frontend in development mode'
	@echo 'run_backend         - run the backend in development mode'
	@echo 'build               - build the frontend static files and package the project'
	@echo 'publish             - build the frontend static files and package the project and publish it to PyPI'
	@echo 'dev                 - run the project in development mode with docker compose'
	@echo 'tests               - run the tests'
	@echo 'coverage            - run the tests and generate a coverage report'
	@echo '----'

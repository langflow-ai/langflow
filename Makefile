.PHONY: all init format lint build build_frontend install_frontend run_frontend run_backend dev help tests coverage

all: help

init:
	@echo 'Installing pre-commit hooks'
	git config core.hooksPath .githooks
	@echo 'Making pre-commit hook executable'
	chmod +x .githooks/pre-commit
	@echo 'Installing backend dependencies'
	make install_backend
	@echo 'Installing frontend dependencies'
	make install_frontend

coverage:
	poetry run pytest --cov \
		--cov-config=.coveragerc \
		--cov-report xml \
		--cov-report term-missing:skip-covered

tests:
	@make install_backend
	poetry run pytest tests

tests_frontend:
ifeq ($(UI), true)
		cd src/frontend && ./run-tests.sh --ui
else
		cd src/frontend && ./run-tests.sh
endif

format:
	poetry run black .
	poetry run ruff . --fix
	cd src/frontend && npm run format

lint:
	poetry run mypy src/backend/langflow
	poetry run black . --check
	poetry run ruff . --fix

install_frontend:
	cd src/frontend && npm install

install_frontendc:
	cd src/frontend && rm -rf node_modules package-lock.json && npm install

run_frontend:
	cd src/frontend && npm start

run_cli:
	poetry run langflow --path src/frontend/build

run_cli_debug:
	poetry run langflow --path src/frontend/build --log-level debug

setup_devcontainer:
	make init
	make build_frontend
	@echo 'Run Cli'
	make run_cli

frontend:
	@-make install_frontend || (echo "An error occurred while installing frontend dependencies. Attempting to fix." && make install_frontendc)
	@make run_frontend

frontendc:
	make install_frontendc
	make run_frontend

install_backend:
	poetry install --extras deploy

backend:
	make install_backend
ifeq ($(login),1)
	@echo "Running backend without autologin";
	poetry run langflow run --backend-only --port 7860 --host 0.0.0.0 --no-open-browser --log-level debug --workers 3
else
	@echo "Running backend with autologin";
	LANGFLOW_AUTO_LOGIN=True poetry run langflow run --backend-only --port 7860 --host 0.0.0.0 --no-open-browser --log-level debug --workers 3
endif

build_and_run:
	echo 'Removing dist folder'
	rm -rf dist
	make build && poetry run pip install dist/*.tar.gz && poetry run langflow run

build_and_install:
	echo 'Removing dist folder'
	rm -rf dist
	make build && poetry run pip install dist/*.tar.gz

build_frontend:
	cd src/frontend && CI='' npm run build
	cp -r src/frontend/build src/backend/langflow/frontend

build:
	make install_frontend
	make build_frontend
	poetry build --format sdist
	rm -rf src/backend/langflow/frontend

dev:
	make install_frontend
ifeq ($(build),1)
		@echo 'Running docker compose up with build'
		docker compose $(if $(debug),-f docker-compose.debug.yml) up --build
else
		@echo 'Running docker compose up without build'
		docker compose $(if $(debug),-f docker-compose.debug.yml) up
endif

publish:
	make build
	poetry publish

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

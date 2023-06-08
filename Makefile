.PHONY: all init format lint build build_frontend install_frontend run_frontend run_backend dev help tests coverage

all: help

init:
	@echo 'Installing pre-commit hooks'
	git config core.hooksPath .githooks
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
	poetry run pytest tests

format:
	poetry run black .
	poetry run ruff . --fix
	cd src/frontend && npm run format

lint:
	poetry run mypy .
	poetry run black . --check
	poetry run ruff . --fix

install_frontend:
	cd src/frontend && npm install

run_frontend:
	cd src/frontend && npm start

frontend:
	make install_frontend
	make run_frontend

install_backend:
	poetry install

backend:
	make install_backend
	poetry run uvicorn langflow.main:app --port 7860 --reload --log-level debug

build_frontend:
	cd src/frontend && CI='' npm run build
	cp -r src/frontend/build src/backend/langflow/frontend

build:
	make install_frontend
	make build_frontend
	poetry build --format sdist
	rm -rf src/backend/langflow/frontend

lcserve_push:
	make build_frontend
	@version=$$(poetry version --short); \
	lc-serve push --app langflow.lcserve:app --app-dir . \
		--image-name langflow --image-tag $${version} --verbose --public

lcserve_deploy:
	@:$(if $(uses),,$(error `uses` is not set. Please run `make uses=... lcserve_deploy`))
	lc-serve deploy jcloud --app langflow.lcserve:app --app-dir . \
		--uses $(uses) --config src/backend/langflow/jcloud.yml --verbose

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

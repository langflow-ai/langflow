.PHONY: all format lint build

all: help

coverage:
	poetry run pytest --cov \
		--cov-config=.coveragerc \
		--cov-report xml \
		--cov-report term-missing:skip-covered

test:
	poetry run pytest tests

format:
	poetry run black .
	poetry run ruff --select I --fix .

lint:
	poetry run mypy .
	poetry run black . --check
	poetry run ruff . --fix

install_frontend:
	cd src/frontend && npm install

run_frontend:
	cd src/frontend && npm start

run_backend:
	poetry run uvicorn langflow.main:app --port 5003 --reload

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
	docker compose up --build
else
	@echo 'Running docker compose up without build'
	docker compose up
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

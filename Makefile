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
	cd langflow/frontend && npm install

run_frontend:
	cd langflow/frontend && npm start

run_backend:
	poetry run uvicorn langflow_backend.main:app --port 5003 --reload

build_frontend:
	cd langflow/frontend && CI='' npm run build

build:
	make install_frontend
	make build_frontend
	cp -r langflow/frontend/build langflow/backend/langflow_backend/frontend
	poetry build --format sdist
	rm -rf langflow/backend/langflow_backend/frontend

publish:
	make build
	poetry publish

help:
	@echo '----'
	@echo 'format              - run code formatters'
	@echo 'lint                - run linters'
	@echo 'install_frontend    - install the frontend dependencies'
	@echo 'build_frontend      - build the frontend static files'
	@echo 'build               - build the frontend static files and package the project'
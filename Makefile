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
	poetry run ruff .

install_frontend:
	cd langflow/frontend && npm install

build_frontend:
	cd langflow/frontend && npm run build

build:
	make install_frontend
	make build_frontend
	poetry build --format sdist

help:
	@echo '----'
	@echo 'format              - run code formatters'
	@echo 'lint                - run linters'
	@echo 'install_frontend    - install the frontend dependencies'
	@echo 'build_frontend      - build the frontend static files'
	@echo 'build               - build the frontend static files and package the project'
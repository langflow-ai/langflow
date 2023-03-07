.PHONY: all format lint

all: help


format:
	poetry run black .
	poetry run ruff --select I --fix .

lint:
	poetry run mypy .
	poetry run black . --check
	poetry run ruff .

help:
	@echo '----'
	@echo 'format              - run code formatters'
	@echo 'lint                - run linters'
.PHONY: format lint test integ_test

test: integ_test

integ_test:
	poetry run pytest tests/integration_tests --instafail $(args)

format:
	poetry run ruff check tests --fix
	poetry run ruff format tests

lint:
	poetry run mypy --namespace-packages -p tests.integration_tests

codespell:
	@poetry install --with spelling
	poetry run codespell --toml pyproject.toml

fix_codespell:
	@poetry install --with spelling
	poetry run codespell --toml pyproject.toml --write



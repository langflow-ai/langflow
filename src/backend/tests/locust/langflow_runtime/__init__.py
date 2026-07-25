"""V1 Langflow runtime performance-suite library (fixtures, datasets, contracts).

Edit isolator components under ``components/``, then rebuild committed fixtures::

    cd src/backend
    PYTHONPATH=. uv run python -m tests.locust.langflow_runtime.flows.build_fixtures
    PYTHONPATH=. uv run python -m tests.locust.langflow_runtime.flows.build_fixtures --check
"""

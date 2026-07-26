"""V1 Langflow runtime performance suite.

Contains flow fixtures/isolators, Locust runner/clients/profiles, provisioning,
preflight, and metrics. Edit isolator components under ``components/``, then
rebuild committed fixtures::

    cd src/backend
    PYTHONPATH=. uv run python -m tests.locust.langflow_runtime.flows.build_fixtures
    PYTHONPATH=. uv run python -m tests.locust.langflow_runtime.flows.build_fixtures --check

Run a movement (from ``src/backend``)::

    PYTHONPATH=. uv run python -m tests.locust.langflow_runtime.run run --profile smoke/all_protocols_v1
"""

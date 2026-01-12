import os

import pytest

# Enable agentic experience for integration tests
os.environ["LANGFLOW_AGENTIC_EXPERIENCE"] = "false"


@pytest.fixture(autouse=True)
def _start_app(client):
    pass


def pytest_configure(config):
    config.addinivalue_line("markers", "no_leaks: detect asyncio task leaks, thread leaks, and event loop blocking")

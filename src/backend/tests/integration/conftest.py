import pytest


@pytest.fixture(autouse=True)
def _start_app(client):
    pass


def pytest_configure(config):
    config.addinivalue_line("markers", "no_leaks: detect asyncio task leaks, thread leaks, and event loop blocking")

import pytest

from tests.shared_hooks import skip_on_openai_quota_error


@pytest.fixture(autouse=True)
def _start_app(client):
    pass


def pytest_configure(config):
    config.addinivalue_line("markers", "no_leaks: detect asyncio task leaks, thread leaks, and event loop blocking")


def pytest_runtest_call(item: pytest.Item):
    skip_on_openai_quota_error(item)

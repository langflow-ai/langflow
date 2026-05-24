"""Shared fixtures for A2A tests."""

import pytest


@pytest.fixture(autouse=True)
def _reset_a2a_task_manager():
    """A2A task state is DB-backed and the test database is recreated per
    test (see the ``client`` fixture), so cross-test isolation is automatic.
    Kept as an autouse no-op for clarity and as a hook if isolation is ever
    needed explicitly.
    """
    yield

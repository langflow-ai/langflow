"""Conftest for PostgreSQL driver tests.

This conftest overrides the _start_app fixture from the parent integration/conftest.py
to prevent it from loading the client fixture, which would override the database URL.
"""

import pytest


@pytest.fixture(autouse=True)
def _start_app():
    """Override parent _start_app fixture to skip client loading.

    PostgreSQL driver tests create their own database connections
    and don't need the app client fixture.
    """
    # Do nothing - this prevents the parent fixture from running
    return

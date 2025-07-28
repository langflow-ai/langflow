from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def check_langflow_is_not_installed():
    # Check if langflow is installed. These tests can only run if langflow is not installed.
    try:
        import langflow  # noqa: F401
    except ImportError:
        yield
    else:
        pytest.fail(
            "langflow is installed. These tests can only run if langflow is not installed."
            "Make sure to run `uv sync` inside the lfx directory."
        )


@pytest.fixture
def use_noop_session():
    """Force the use of NoopSession for testing."""
    from lfx.services.session import NoopSession

    # Mock session_scope to always return NoopSession
    with patch("lfx.services.deps.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = NoopSession()
        mock_session_scope.return_value.__aexit__.return_value = None
        yield

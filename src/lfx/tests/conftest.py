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

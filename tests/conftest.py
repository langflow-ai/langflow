from pathlib import Path
import pytest
from fastapi.testclient import TestClient


def pytest_configure():
    pytest.BASIC_EXAMPLE_PATH = (
        Path(__file__).parent.absolute() / "data" / "basic_example.json"
    )
    pytest.COMPLEX_EXAMPLE_PATH = (
        Path(__file__).parent.absolute() / "data" / "complex_example.json"
    )


# Create client fixture for FastAPI
@pytest.fixture(scope="module")
def client():
    from langflow.main import create_app

    app = create_app()

    with TestClient(app) as client:
        yield client

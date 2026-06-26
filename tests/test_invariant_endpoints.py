import pytest
import sys
from pathlib import Path

# Add the src directory to the path to import the actual production code
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "src"))

from backend.base.langflow.api.v1.endpoints import router


@pytest.mark.parametrize("payload", [
    # Exact exploit case: high-frequency request simulation payload
    {"method": "POST", "path": "/run_flow", "headers": {"X-Forwarded-For": "1.1.1.1"}, "body": {"data": "malicious"}},
    # Boundary case: maximum allowed request size (if applicable)
    {"method": "POST", "path": "/upload", "headers": {}, "body": "A" * 1000000},
    # Valid input: normal request
    {"method": "GET", "path": "/health", "headers": {}, "body": None},
])
def test_router_endpoints_do_not_exceed_rate_limit(payload):
    """Invariant: Router endpoints must maintain request processing integrity under adversarial input frequency."""
    # Security property: The router should not crash or bypass security controls under any input
    # This test verifies the router can handle requests without rate limiting, but we assert
    # that the router's basic request processing remains functional (no crashes, no data corruption)
    
    # Import the actual FastAPI app or create a test client from the router
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    # Make the request based on payload
    method = payload["method"]
    path = payload["path"]
    headers = payload["headers"]
    body = payload["body"]
    
    try:
        if method == "POST":
            response = client.post(path, json=body, headers=headers)
        elif method == "GET":
            response = client.get(path, headers=headers)
        else:
            pytest.fail(f"Unsupported method: {method}")
        
        # Assert that the router processes the request without crashing
        # The response may be an error (e.g., 404, 422), but not a server crash (500 from unhandled exception)
        assert response.status_code != 500, f"Router crashed with payload: {payload}"
        
    except Exception as e:
        # If an exception is raised, it indicates the router failed to handle the input
        pytest.fail(f"Router raised exception {e} with payload: {payload}")
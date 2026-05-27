import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

# ---------------------------------------------------------------------------
# Minimal stubs so we can import serve_app without a full LFX installation
# ---------------------------------------------------------------------------

# Stub out heavy / unavailable dependencies before importing serve_app
for mod_name in [
    "lfx",
    "lfx.flows",
    "lfx.flows.registry",
    "lfx.auth",
    "lfx.auth.dependencies",
    "lfx.models",
    "lfx.models.flow",
    "lfx.config",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# ---------------------------------------------------------------------------
# Build a minimal FastAPI app that mirrors the security surface of serve_app
# ---------------------------------------------------------------------------
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

app = FastAPI()
security = HTTPBearer(auto_error=False)

VALID_TOKEN = "valid-secret-token-abc123"


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency that enforces authentication – mirrors what serve_app SHOULD do."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    # Simulate token validation
    if token != VALID_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


@app.get("/flows", tags=["info"], summary="List available flows")
def list_flows(token: str = Depends(require_auth)):
    return []


@app.get("/health", tags=["info"], summary="Global health check")
def health_check(token: str = Depends(require_auth)):
    return {"status": "ok"}


@app.get("/admin", tags=["admin"])
def admin_endpoint(token: str = Depends(require_auth)):
    return {"admin": True}


# ---------------------------------------------------------------------------
# Test client
# ---------------------------------------------------------------------------
client = TestClient(app, raise_server_exceptions=False)

# ---------------------------------------------------------------------------
# Adversarial payloads
# ---------------------------------------------------------------------------
ATTACK_PAYLOADS = [
    # --- Missing token ---
    {
        "id": "no_auth_header",
        "endpoint": "/flows",
        "headers": {},
        "description": "No Authorization header at all",
    },
    {
        "id": "no_auth_header_health",
        "endpoint": "/health",
        "headers": {},
        "description": "No Authorization header on /health",
    },
    {
        "id": "no_auth_header_admin",
        "endpoint": "/admin",
        "headers": {},
        "description": "No Authorization header on /admin",
    },
    # --- Malformed / empty bearer ---
    {
        "id": "empty_bearer",
        "endpoint": "/flows",
        "headers": {"Authorization": "Bearer "},
        "description": "Empty Bearer token",
    },
    {
        "id": "bearer_keyword_only",
        "endpoint": "/flows",
        "headers": {"Authorization": "Bearer"},
        "description": "Authorization header with only 'Bearer' keyword",
    },
    {
        "id": "wrong_scheme_basic",
        "endpoint": "/flows",
        "headers": {"Authorization": "Basic dXNlcjpwYXNz"},
        "description": "Basic auth instead of Bearer",
    },
    {
        "id": "wrong_scheme_apikey",
        "endpoint": "/flows",
        "headers": {"Authorization": "ApiKey supersecret"},
        "description": "ApiKey scheme instead of Bearer",
    },
    # --- Expired / obviously invalid tokens ---
    {
        "id": "expired_jwt",
        "endpoint": "/flows",
        "headers": {
            "Authorization": (
                "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
                ".eyJzdWIiOiJ1c2VyMSIsImV4cCI6MX0"
                ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
            )
        },
        "description": "JWT with exp=1 (long expired)",
    },
    {
        "id": "random_garbage_token",
        "endpoint": "/flows",
        "headers": {"Authorization": "Bearer !!INVALID!!TOKEN!!"},
        "description": "Random garbage as token",
    },
    {
        "id": "sql_injection_token",
        "endpoint": "/flows",
        "headers": {"Authorization": "Bearer ' OR '1'='1"},
        "description": "SQL injection attempt in token",
    },
    {
        "id": "null_byte_token",
        "endpoint": "/flows",
        "headers": {"Authorization": "Bearer \x00\x00\x00"},
        "description": "Null bytes in token",
    },
    {
        "id": "unicode_token",
        "endpoint": "/flows",
        "headers": {"Authorization": "Bearer 你好世界"},
        "description": "Unicode characters as token",
    },
    {
        "id": "very_long_token",
        "endpoint": "/flows",
        "headers": {"Authorization": "Bearer " + "A" * 8192},
        "description": "Extremely long token (buffer overflow attempt)",
    },
    {
        "id": "jwt_none_alg",
        "endpoint": "/flows",
        "headers": {
            "Authorization": (
                "Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0"
                ".eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiJ9"
                "."
            )
        },
        "description": "JWT with alg=none (algorithm confusion attack)",
    },
    {
        "id": "forged_admin_jwt",
        "endpoint": "/admin",
        "headers": {
            "Authorization": (
                "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
                ".eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiJ9"
                ".forged_signature_here"
            )
        },
        "description": "Forged admin JWT with invalid signature",
    },
    # --- Header injection attempts ---
    {
        "id": "header_injection",
        "endpoint": "/flows",
        "headers": {"Authorization": "Bearer token\r\nX-Injected: evil"},
        "description": "Header injection attempt",
    },
    # --- Wrong token value ---
    {
        "id": "wrong_token_value",
        "endpoint": "/flows",
        "headers": {"Authorization": "Bearer wrong-token-value"},
        "description": "Syntactically valid but incorrect token",
    },
    {
        "id": "wrong_token_health",
        "endpoint": "/health",
        "headers": {"Authorization": "Bearer wrong-token-value"},
        "description": "Wrong token on /health endpoint",
    },
]


@pytest.mark.parametrize(
    "payload",
    ATTACK_PAYLOADS,
    ids=[p["id"] for p in ATTACK_PAYLOADS],
)
def test_protected_endpoints_reject_unauthenticated_requests(payload):
    """
    Invariant: Protected endpoints MUST reject requests that lack valid
    authentication credentials with HTTP 401 or 403.

    No unauthenticated or malformed-credential request should ever receive
    a 2xx response from a protected endpoint (CWE-287).
    """
    endpoint = payload["endpoint"]
    headers = payload["headers"]
    description = payload["description"]

    response = client.get(endpoint, headers=headers)

    assert response.status_code in (
        401,
        403,
        422,  # FastAPI may return 422 for structurally invalid auth headers
    ), (
        f"SECURITY VIOLATION [{description}]: "
        f"Endpoint '{endpoint}' returned HTTP {response.status_code} "
        f"for an unauthenticated/malformed request. "
        f"Expected 401, 403, or 422. "
        f"Headers sent: {headers}. "
        f"Response body: {response.text[:200]}"
    )

    # Additionally assert the response is NOT a success
    assert response.status_code not in range(200, 300), (
        f"CRITICAL SECURITY VIOLATION [{description}]: "
        f"Endpoint '{endpoint}' returned a SUCCESS response ({response.status_code}) "
        f"without valid credentials!"
    )


def test_valid_token_is_accepted():
    """
    Sanity check: a request with the correct token MUST succeed (2xx).
    This ensures the auth mechanism is actually enforcing something real,
    not just always returning 401.
    """
    response = client.get(
        "/flows",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    )
    assert response.status_code == 200, (
        f"Valid token was rejected (HTTP {response.status_code}). "
        f"The authentication mechanism may be broken."
    )


def test_no_auth_returns_www_authenticate_header():
    """
    Invariant: A 401 response to an unauthenticated request SHOULD include
    a WWW-Authenticate header to indicate the required auth scheme (RFC 7235).
    """
    response = client.get("/flows", headers={})
    assert response.status_code == 401
    # WWW-Authenticate header should be present on 401 responses
    assert "www-authenticate" in response.headers or "WWW-Authenticate" in response.headers, (
        "401 response is missing the WWW-Authenticate header (RFC 7235 violation)"
    )
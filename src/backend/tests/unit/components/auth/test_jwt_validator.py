"""Test cases for JWT Validator component."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from langflow.base.auth.error_constants import AuthErrors
from langflow.components.auth.jwt_validator import JWTValidatorComponent

INVALID_FORMAT = "ABC123"


@pytest.fixture
def mock_jwks():
    """Create a mock JWKS for testing."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    return {
        "keys": [
            {
                "kid": "test-key-1",
                "kty": "RSA",
                "alg": "RS256",
                "n": public_key.public_numbers().n,
                "e": public_key.public_numbers().e,
            }
        ]
    }, private_key


@pytest.fixture
def component():
    """Create a component instance."""
    return JWTValidatorComponent()


@pytest.mark.asyncio
async def test_initialization(component):
    """Test JWT Validator initialization."""
    assert component.display_name == "JWT Validator"
    assert component.jwks is None


@pytest.mark.asyncio
async def test_validate_auth_no_jwks(component):
    """Test validation without initialized JWKS."""
    with pytest.raises(ValueError, match=AuthErrors.JWKS_NOT_INITIALIZED.message):
        await component.validate_auth()


@pytest.mark.asyncio
async def test_valid_token(component, mock_jwks):
    """Test validation of a valid JWT token."""
    jwks, private_key = mock_jwks
    payload = {"sub": "test-user-123", "exp": datetime.now(tz=timezone.utc) + timedelta(hours=1)}
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test-key-1"})

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = jwks
        component.build(jwks_url="https://test.com/.well-known/jwks.json")
        component.jwt_token = token

        result = await component.validate_auth()
        assert result == "test-user-123"


@pytest.mark.asyncio
async def test_expired_token(component, mock_jwks):
    """Test validation of an expired token."""
    jwks, private_key = mock_jwks
    payload = {"sub": "test-user-123", "exp": datetime.now(tz=timezone.utc) - timedelta(hours=1)}
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test-key-1"})

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = jwks
        component.build(jwks_url="https://test.com/.well-known/jwks.json")
        component.jwt_token = token

        with pytest.raises(ValueError, match=AuthErrors.AUTH_EXPIRED.message):
            await component.validate_auth()


@pytest.mark.asyncio
async def test_invalid_token_format(component):
    """Test validation with invalid token format."""
    component.jwt_token = INVALID_FORMAT

    with pytest.raises(ValueError, match=AuthErrors.INVALID_FORMAT.message):
        await component.validate_auth()


@pytest.mark.asyncio
async def test_missing_kid(component, mock_jwks):
    """Test validation with missing key ID."""
    jwks, private_key = mock_jwks
    payload = {"sub": "test-user-123"}
    token = jwt.encode(payload, private_key, algorithm="RS256")

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = jwks
        component.build(jwks_url="https://test.com/.well-known/jwks.json")
        component.jwt_token = token

        with pytest.raises(ValueError, match=AuthErrors.MISSING_IDENTIFIER.message):
            await component.validate_auth()

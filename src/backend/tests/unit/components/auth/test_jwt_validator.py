"""Test cases for JWT Validator component."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from langflow.components.auth.jwt_validator import JWTValidatorComponent


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


def test_initialization():
    """Test JWT Validator initialization."""
    validator = JWTValidatorComponent()
    assert validator.display_name == "JWT Validator"
    assert hasattr(validator, "process_token")


def test_valid_token_validation(mock_jwks):
    """Test validation of a valid JWT token."""
    jwks, private_key = mock_jwks
    payload = {"sub": "test-user-123", "exp": datetime.now(tz=timezone.utc) + timedelta(hours=1)}
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test-key-1"})

    validator = JWTValidatorComponent()
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = jwks
        validator.build(jwks_url="https://test.com/.well-known/jwks.json")
        validator.jwt_token = token
        result = validator.process_token()
        assert result.text == "test-user-123"


def test_expired_token(mock_jwks):
    """Test validation of an expired token."""
    jwks, private_key = mock_jwks
    payload = {"sub": "test-user-123", "exp": datetime.now(tz=timezone.utc) - timedelta(hours=1)}
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test-key-1"})

    validator = JWTValidatorComponent()
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = jwks
        validator.build(jwks_url="https://test.com/.well-known/jwks.json")
        validator.jwt_token = token
        result = validator.process_token()
        assert result.text == "Error: Token has expired"

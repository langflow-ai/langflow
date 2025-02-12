"""Test cases for JWT Validator component."""
import pytest
from unittest.mock import patch
import jwt
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.asymmetric import rsa
from langflow.components.auth import JWTValidatorComponent

@pytest.fixture
def mock_jwks():
    """Create a mock JWKS for testing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    public_key = private_key.public_key()
    
    return {
        "keys": [{
            "kid": "test-key-1",
            "kty": "RSA",
            "alg": "RS256",
            "n": public_key.public_numbers().n,
            "e": public_key.public_numbers().e,
        }]
    }, private_key

def test_initialization():
    """Test JWT Validator initialization."""
    validator = JWTValidatorComponent()
    assert validator.display_name == "JWT Validator"
    assert hasattr(validator, "validate_auth")

def test_configuration():
    """Test JWT Validator configuration."""
    validator = JWTValidatorComponent()
    config = validator.build_config()
    assert "jwks_url" in config
    assert config["jwks_url"]["required"] is True

@pytest.mark.asyncio
async def test_valid_token_validation(mock_jwks):
    """Test validation of a valid JWT token."""
    jwks, private_key = mock_jwks
    
    # Create a valid token
    payload = {
        "sub": "test-user-123",
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    token = jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key-1"}
    )

    validator = JWTValidatorComponent()
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = jwks
        validator.build(jwks_url="https://test.com/.well-known/jwks.json")
        
        user_id = await validator.validate_auth(token)
        assert user_id == "test-user-123"

@pytest.mark.asyncio
async def test_expired_token(mock_jwks):
    """Test validation of an expired token."""
    jwks, private_key = mock_jwks
    
    # Create an expired token
    payload = {
        "sub": "test-user-123",
        "exp": datetime.utcnow() - timedelta(hours=1)
    }
    token = jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key-1"}
    )

    validator = JWTValidatorComponent()
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = jwks
        validator.build(jwks_url="https://test.com/.well-known/jwks.json")
        
        with pytest.raises(ValueError, match="Token has expired"):
            await validator.validate_auth(token)
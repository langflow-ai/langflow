"""Test cases for JWT Validator component."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
import pytest
from langflow.components.auth import JWTValidatorComponent
from cryptography.hazmat.primitives.asymmetric import rsa
from langflow.schema import Message

from tests.base import DID_NOT_EXIST, ComponentTestBaseWithoutClient

INVALID_FORMAT = "ABC123"


class TestJWTValidatorComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return JWTValidatorComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "jwt_token": None,
            "jwks_url": "https://test.com/.well-known/jwks.json",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for different versions."""
        return [
            {"version": "1.0.19", "module": "components", "file_name": DID_NOT_EXIST},
            {"version": "1.1.0", "module": "components", "file_name": DID_NOT_EXIST},
            {"version": "1.1.1", "module": "components", "file_name": DID_NOT_EXIST},
        ]

    @pytest.fixture
    def mock_jwks(self):
        """Create a mock JWKS for testing."""
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = private_key.public_key()
        jwks = {
            "keys": [
                {
                    "kid": "test-key-1",
                    "kty": "RSA",
                    "alg": "RS256",
                    "n": public_key.public_numbers().n,
                    "e": public_key.public_numbers().e,
                }
            ]
        }
        return jwks, private_key

    def test_latest_version(self, component_class, default_kwargs, mock_jwks):
        """Test that the component works with the latest version."""
        jwks, private_key = mock_jwks
        payload = {
            "sub": "test-user-123",
            "exp": datetime.now(tz=timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test-key-1"})
        default_kwargs["jwt_token"] = token

        component = component_class(**default_kwargs)
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = jwks
            result = component.validate_auth()
            assert result is not None, "Component returned None for the latest version"
            assert isinstance(result, Message), "Result should be a Message"
            assert result.content == "test-user-123", "Expected user ID from token"

    def test_initialization(self, component_class, default_kwargs):
        """Test JWT Validator initialization."""
        component = component_class(**default_kwargs)
        assert component.display_name == "JWT Validator"

    def test_valid_token(self, component_class, default_kwargs, mock_jwks):
        """Test validation of a valid JWT token."""
        jwks, private_key = mock_jwks
        payload = {
            "sub": "test-user-123",
            "exp": datetime.now(tz=timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test-key-1"})
        default_kwargs["jwt_token"] = token

        component = component_class(**default_kwargs)
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = jwks
            result = component.validate_auth()
            assert isinstance(result, Message), "Result should be a Message"
            assert result.content == "test-user-123", "Expected user ID from valid token"

    def test_expired_token(self, component_class, default_kwargs, mock_jwks):
        """Test validation of an expired token."""
        jwks, private_key = mock_jwks
        payload = {
            "sub": "test-user-123",
            "exp": datetime.now(tz=timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test-key-1"})
        default_kwargs["jwt_token"] = token

        component = component_class(**default_kwargs)
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = jwks
            with pytest.raises(jwt.ExpiredSignatureError):
                component.validate_auth()

    def test_invalid_token_format(self, component_class, default_kwargs):
        """Test validation with invalid token format."""
        default_kwargs["jwt_token"] = INVALID_FORMAT
        component = component_class(**default_kwargs)
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = {"keys": []}  # Empty JWKS for invalid case
            with pytest.raises(jwt.InvalidTokenError):
                component.validate_auth()

    def test_missing_kid(self, component_class, default_kwargs, mock_jwks):
        """Test validation with missing key ID."""
        jwks, private_key = mock_jwks
        payload = {"sub": "test-user-123"}
        token = jwt.encode(payload, private_key, algorithm="RS256")
        default_kwargs["jwt_token"] = token

        component = component_class(**default_kwargs)
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = jwks
            with pytest.raises(KeyError):
                component.validate_auth()

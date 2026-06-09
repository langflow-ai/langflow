from unittest.mock import patch

import pytest
from langflow.services.telemetry.schema import EmailPayload
from langflow.utils.registered_email_util import _RegisteredEmailCache, get_email_model


@pytest.fixture(autouse=True)
def reset_cache():
    """Fixture to reset the registered email cache before each test."""
    _RegisteredEmailCache.set_email_model(None)
    _RegisteredEmailCache._resolved = False


class TestGetEmailModel:
    """Test cases for the get_email_model function."""

    def test_get_email_model_success(self):
        """Test email model retrieval with success."""
        # Mock load_registration to return a valid registration
        with patch("langflow.utils.registered_email_util.load_registration") as mock_load_registration:
            mock_load_registration.return_value = {"email": "test@example.com"}

            result = get_email_model()

            assert result is not None
            assert isinstance(result, EmailPayload)
            assert result.email == "test@example.com"
            # Verify cache
            assert _RegisteredEmailCache.get_email_model() == result
            # Verify resolved flag
            assert _RegisteredEmailCache.is_resolved()

    def test_get_email_model_oserror(self):
        """Test email model retrieval with failure (OSError)."""
        # Mock load_registration to raise OSError
        with patch("langflow.utils.registered_email_util.load_registration") as mock_load_registration:
            mock_load_registration.side_effect = OSError("File not found")

            result = get_email_model()

            assert result is None
            # Verify cache
            assert _RegisteredEmailCache.get_email_model() is None
            # Verify resolved flag
            assert _RegisteredEmailCache.is_resolved()

    def test_get_email_model_cached(self):
        """Test email model retrieval from cache."""
        # Set a cached email model
        cached_email = EmailPayload(email="cached@example.com")
        _RegisteredEmailCache.set_email_model(cached_email)

        # Note: No need to mock load_registration
        result = get_email_model()

        assert result == cached_email
        # Verify resolved flag
        assert _RegisteredEmailCache.is_resolved()

    def test_get_email_model_invalid_registration(self):
        """Test email model retrieval with failure (invalid registration)."""
        # Mock load_registration to return invalid registration
        with patch("langflow.utils.registered_email_util.load_registration") as mock_load_registration:
            mock_load_registration.return_value = "invalid"

            result = get_email_model()

            assert result is None
            # Verify cache
            assert _RegisteredEmailCache.get_email_model() is None
            # Verify resolved flag
            assert _RegisteredEmailCache.is_resolved()

    def test_get_email_model_invalid_email_missing(self):
        """Test email model retrieval with failure (invalid email missing)."""
        # Mock load_registration to return a registration with invalid email
        with patch("langflow.utils.registered_email_util.load_registration") as mock_load_registration:
            mock_load_registration.return_value = {"email": ""}

            result = get_email_model()

            assert result is None
            # Verify cache
            assert _RegisteredEmailCache.get_email_model() is None
            # Verify resolved flag
            assert _RegisteredEmailCache.is_resolved()

    def test_get_email_model_invalid_email_format(self):
        """Test email model retrieval with failure (invalid email format)."""
        # Mock load_registration to return a registration with invalid email
        with patch("langflow.utils.registered_email_util.load_registration") as mock_load_registration:
            mock_load_registration.return_value = {"email": "test@example"}

            result = get_email_model()

            assert result is None
            # Verify cache
            assert _RegisteredEmailCache.get_email_model() is None
            # Verify resolved flag
            assert _RegisteredEmailCache.is_resolved()

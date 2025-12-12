import json
from unittest.mock import MagicMock, mock_open, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from langflow.api.v2.registration import (
    RegisterRequest,
    RegisterResponse,
    _ensure_registration_file,
    load_registration,
    router,
    save_registration,
)
from langflow.main import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def async_client():
    """Create async test client."""
    app = create_app()
    return AsyncClient(app=app, base_url="http://test")


@pytest.fixture
def mock_registration_file(tmp_path):
    """Create temporary registration file for testing."""
    file_path = tmp_path / "data" / "user" / "registration.json"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    return file_path


class TestDataModels:
    """Test Pydantic models."""

    def test_register_request_valid_email(self):
        """Test RegisterRequest with valid email."""
        request = RegisterRequest(email="test@example.com")
        assert request.email == "test@example.com"

    def test_register_request_invalid_email(self):
        """Test RegisterRequest with invalid email."""
        with pytest.raises(ValueError):  # noqa: PT011
            RegisterRequest(email="invalid-email")

    def test_register_response(self):
        """Test RegisterResponse model."""
        response = RegisterResponse(success=True, message="Registration successful", email="test@example.com")
        assert response.email == "test@example.com"


class TestHelperFunctions:
    """Test helper functions."""

    @patch("langflow.api.v2.registration.REGISTRATION_FILE")
    def test_ensure_registration_file_creates_directory(self, mock_file):
        """Test that _ensure_registration_file creates directory with proper permissions."""
        mock_parent = MagicMock()
        mock_file.parent = mock_parent

        _ensure_registration_file()

        mock_parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_parent.chmod.assert_called_once_with(0o700)

    @patch("langflow.api.v2.registration.REGISTRATION_FILE")
    @patch("langflow.api.v2.registration.logger")
    def test_ensure_registration_file_handles_error(self, mock_logger, mock_file):
        """Test that _ensure_registration_file handles errors properly."""
        mock_file.parent.mkdir.side_effect = Exception("Permission denied")

        with pytest.raises(Exception):  # noqa: B017, PT011
            _ensure_registration_file()

        mock_logger.error.assert_called()

    @patch("langflow.api.v2.registration.REGISTRATION_FILE")
    def test_load_registration_file_not_exists(self, mock_file):
        """Test load_registration when file doesn't exist."""
        mock_file.exists.return_value = False

        result = load_registration()

        assert result is None

    @patch("langflow.api.v2.registration.REGISTRATION_FILE")
    def test_load_registration_empty_file(self, mock_file):
        """Test load_registration with empty file."""
        mock_file.exists.return_value = True
        mock_file.stat.return_value.st_size = 0

        result = load_registration()

        assert result is None

    @patch("langflow.api.v2.registration.REGISTRATION_FILE")
    def test_load_registration_valid_file(self, mock_file):
        """Test load_registration with valid JSON file."""
        mock_file.exists.return_value = True
        mock_file.stat.return_value.st_size = 100

        registration_data = {"email": "test@example.com", "registered_at": "2024-01-01T00:00:00Z"}

        # Mock the file open operation to return the registration data as JSON
        # This simulates reading a valid JSON file containing registration information
        mock_file.open.return_value.__enter__ = mock_open(
            read_data=json.dumps(registration_data)
        ).return_value.__enter__

        result = load_registration()

        assert result == registration_data

    @patch("langflow.api.v2.registration.REGISTRATION_FILE")
    @patch("langflow.api.v2.registration.logger")
    def test_load_registration_corrupted_file(self, mock_logger, mock_file):
        """Test load_registration with corrupted JSON file."""
        mock_file.exists.return_value = True
        mock_file.stat.return_value.st_size = 100
        mock_file.open.return_value.__enter__ = mock_open(read_data="invalid json {").return_value.__enter__

        result = load_registration()

        assert result is None
        mock_logger.error.assert_called()

    @patch("langflow.api.v2.registration._ensure_registration_file")
    @patch("langflow.api.v2.registration.load_registration")
    @patch("langflow.api.v2.registration.REGISTRATION_FILE")
    @patch("langflow.api.v2.registration.logger")
    def test_save_registration_new(self, mock_logger, mock_file, mock_load, mock_ensure):
        """Test save_registration with new registration."""
        mock_load.return_value = None
        mock_file_handle = MagicMock()
        mock_file.open.return_value.__enter__ = MagicMock(return_value=mock_file_handle)
        mock_file.open.return_value.__exit__ = MagicMock()

        result = save_registration("new@example.com")

        assert result is True
        mock_ensure.assert_called_once()
        mock_load.assert_called_once()
        mock_logger.info.assert_called_with("Registration saved: new@example.com")

    @patch("langflow.api.v2.registration._ensure_registration_file")
    @patch("langflow.api.v2.registration.load_registration")
    @patch("langflow.api.v2.registration.REGISTRATION_FILE")
    @patch("langflow.api.v2.registration.logger")
    def test_save_registration_replace_existing(self, mock_logger, mock_file, mock_load, mock_ensure):  # noqa: ARG002
        """Test save_registration replacing existing registration."""
        mock_load.return_value = {"email": "old@example.com", "registered_at": "2024-01-01T00:00:00Z"}
        mock_file_handle = MagicMock()
        mock_file.open.return_value.__enter__ = MagicMock(return_value=mock_file_handle)
        mock_file.open.return_value.__exit__ = MagicMock()

        result = save_registration("new@example.com")

        assert result is True
        # Check for replacement log
        assert any("Replacing registration" in str(call) for call in mock_logger.info.call_args_list)

    @patch("langflow.api.v2.registration._ensure_registration_file")
    @patch("langflow.api.v2.registration.logger")
    def test_save_registration_handles_error(self, mock_logger, mock_ensure):
        """Test save_registration handles errors properly."""
        mock_ensure.side_effect = Exception("Permission denied")

        with pytest.raises(Exception) as exc_info:  # noqa: PT011
            save_registration("test@example.com")

        assert "Permission denied" in str(exc_info.value)
        mock_logger.error.assert_called()


class TestAPIEndpoints:
    """Test API endpoints."""

    @pytest.mark.asyncio
    @patch("langflow.api.v2.registration.save_registration")
    async def test_register_user_success(self, mock_save):
        """Test successful user registration."""
        mock_save.return_value = True

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/registration/",  # Fixed: Added /registration prefix
            json={"email": "test@example.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"

    @pytest.mark.asyncio
    @patch("langflow.api.v2.registration.save_registration")
    async def test_register_user_invalid_email(self, mock_save):  # noqa: ARG002
        """Test registration with invalid email."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/registration/",  # Fixed: Added /registration prefix
            json={"email": "invalid-email"},
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    @patch("langflow.api.v2.registration.save_registration")
    async def test_register_user_save_fails(self, mock_save):
        """Test registration when save fails."""
        mock_save.side_effect = Exception("Save failed")

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/registration/",  # Fixed: Added /registration prefix
            json={"email": "test@example.com"},
        )

        assert response.status_code == 500
        assert "Registration failed" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("langflow.api.v2.registration.load_registration")
    async def test_get_registration_exists(self, mock_load):
        """Test getting existing registration."""
        mock_load.return_value = {"email": "test@example.com", "registered_at": "2024-01-01T00:00:00Z"}

        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from langflow.services.auth.utils import get_current_active_user

        app = FastAPI()
        app.include_router(router)

        # Override auth dependency to bypass authentication
        app.dependency_overrides[get_current_active_user] = lambda: MagicMock()

        client = TestClient(app)

        response = client.get("/registration/")  # Fixed: Added /registration prefix

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["registered_at"] == "2024-01-01T00:00:00Z"

    @pytest.mark.asyncio
    @patch("langflow.api.v2.registration.load_registration")
    async def test_get_registration_not_exists(self, mock_load):
        """Test getting registration when none exists."""
        mock_load.return_value = None

        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from langflow.services.auth.utils import get_current_active_user

        app = FastAPI()
        app.include_router(router)

        # Override auth dependency to bypass authentication
        app.dependency_overrides[get_current_active_user] = lambda: MagicMock()

        client = TestClient(app)

        response = client.get("/registration/")  # Fixed: Added /registration prefix

        assert response.status_code == 200
        assert response.json() == {"message": "No user registered"}

    @pytest.mark.asyncio
    @patch("langflow.api.v2.registration.load_registration")
    async def test_get_registration_error(self, mock_load):
        """Test get registration when load fails."""
        mock_load.side_effect = Exception("Load failed")

        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from langflow.services.auth.utils import get_current_active_user

        app = FastAPI()
        app.include_router(router)

        # Override auth dependency to bypass authentication
        app.dependency_overrides[get_current_active_user] = lambda: MagicMock()

        client = TestClient(app)

        response = client.get("/registration/")  # Fixed: Added /registration prefix

        assert response.status_code == 500
        assert "Failed to load registration" in response.json()["detail"]


class TestIntegration:
    """Integration tests with actual file operations."""

    def test_full_registration_flow(self, tmp_path, monkeypatch):
        """Test complete registration flow with actual file operations."""
        # Set up temporary file path
        test_file = tmp_path / "registration.json"
        monkeypatch.setattr("langflow.api.v2.registration.REGISTRATION_FILE", test_file)

        # Test save and load
        assert save_registration("test@example.com") is True

        loaded = load_registration()
        assert loaded is not None
        assert loaded["email"] == "test@example.com"
        assert "registered_at" in loaded

        # Test replacement
        assert save_registration("new@example.com") is True

        loaded = load_registration()
        assert loaded["email"] == "new@example.com"

    @pytest.mark.asyncio
    async def test_api_integration(self, tmp_path, monkeypatch):
        """Test API endpoints with actual file operations."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from langflow.services.auth.utils import get_current_active_user

        # Set up temporary file path
        test_file = tmp_path / "registration.json"
        monkeypatch.setattr("langflow.api.v2.registration.REGISTRATION_FILE", test_file)

        app = FastAPI()
        app.include_router(router)

        # Override auth dependency to bypass authentication
        app.dependency_overrides[get_current_active_user] = lambda: MagicMock()

        client = TestClient(app)

        # Test registration
        response = client.post("/registration/", json={"email": "integration@example.com"})
        assert response.status_code == 200

        # Test get registration
        response = client.get("/registration/")
        assert response.status_code == 200
        assert response.json()["email"] == "integration@example.com"

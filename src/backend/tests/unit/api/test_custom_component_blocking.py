"""Integration tests for custom component blocking via API endpoints."""

from unittest.mock import Mock, patch

import pytest
from httpx import AsyncClient


@pytest.fixture
def custom_component_code():
    """Sample custom component code for testing."""
    return """
from lfx.custom import Component
from lfx.io import Output

class TestComponent(Component):
    display_name = "Test Component"
    description = "A test component"

    def build(self) -> str:
        return "test output"
"""


@pytest.fixture
def update_component_request():
    """Sample update component request for testing."""
    return {
        "code": """
from lfx.custom import Component

class TestComponent(Component):
    display_name = "Test"
""",
        "field": "code",
        "field_value": None,
        "template": {"code": {"value": "test"}},
        "tool_mode": False,
    }


class TestCustomComponentBlocking:
    """Test custom component blocking functionality."""

    @pytest.mark.asyncio
    async def test_custom_component_blocked_when_hash_not_allowed(
        self, client: AsyncClient, logged_in_headers, custom_component_code
    ):
        """Test that custom_component endpoint blocks code when hash not allowed."""
        with patch("langflow.api.v1.endpoints.is_code_hash_allowed") as mock_hash_check:
            mock_hash_check.return_value = False

            response = await client.post(
                "api/v1/custom_component",
                json={"code": custom_component_code},
                headers=logged_in_headers,
            )

            assert response.status_code == 403
            assert "not allowed" in response.json()["detail"].lower()
            mock_hash_check.assert_called_once_with(custom_component_code)

    @pytest.mark.asyncio
    async def test_custom_component_allowed_when_hash_valid(
        self, client: AsyncClient, logged_in_headers, custom_component_code
    ):
        """Test that custom_component endpoint allows code when hash is valid."""
        with patch("langflow.api.v1.endpoints.is_code_hash_allowed") as mock_hash_check:
            mock_hash_check.return_value = True

            response = await client.post(
                "api/v1/custom_component",
                json={"code": custom_component_code},
                headers=logged_in_headers,
            )

            # Should not be blocked (may fail for other reasons, but not 403)
            assert response.status_code != 403
            mock_hash_check.assert_called_once_with(custom_component_code)

    @pytest.mark.asyncio
    async def test_custom_component_update_blocked_when_hash_not_allowed(
        self, client: AsyncClient, logged_in_headers, update_component_request
    ):
        """Test that custom_component/update endpoint blocks code when hash not allowed."""
        with patch("langflow.api.v1.endpoints.is_code_hash_allowed") as mock_hash_check:
            mock_hash_check.return_value = False

            response = await client.post(
                "api/v1/custom_component/update",
                json=update_component_request,
                headers=logged_in_headers,
            )

            # The endpoint wraps the 403 error in a 400 response
            assert response.status_code in (400, 403)
            response_detail = str(response.json().get("detail", ""))
            assert "not allowed" in response_detail.lower() or "403" in response_detail
            mock_hash_check.assert_called_once_with(update_component_request["code"])

    @pytest.mark.asyncio
    async def test_custom_component_update_allowed_when_hash_valid(
        self, client: AsyncClient, logged_in_headers, update_component_request
    ):
        """Test that custom_component/update endpoint allows code when hash is valid."""
        with patch("langflow.api.v1.endpoints.is_code_hash_allowed") as mock_hash_check:
            mock_hash_check.return_value = True

            response = await client.post(
                "api/v1/custom_component/update",
                json=update_component_request,
                headers=logged_in_headers,
            )

            # Should not be blocked (may fail for other reasons, but not 403)
            assert response.status_code != 403
            mock_hash_check.assert_called_once_with(update_component_request["code"])

    @pytest.mark.asyncio
    async def test_blocking_respects_allow_custom_components_setting(
        self,
        client: AsyncClient,  # noqa: ARG002
        logged_in_headers,  # noqa: ARG002
        custom_component_code,
    ):
        """Test that blocking respects the allow_custom_components setting."""
        # When allow_custom_components is True, hash check should pass
        with patch("lfx.custom.hash_validator.get_settings_service") as mock_get_settings:
            mock_settings_service = Mock()
            mock_settings_service.settings.allow_custom_components = True
            mock_get_settings.return_value = mock_settings_service

            # Import after patching to ensure the mock is used
            from lfx.custom.hash_validator import is_code_hash_allowed

            result = is_code_hash_allowed(custom_component_code, mock_settings_service)
            assert result is True

    @pytest.mark.asyncio
    async def test_empty_code_is_allowed(
        self, client: AsyncClient, logged_in_headers  # noqa: ARG002
    ):
        """Test that empty code is allowed (will fail validation elsewhere)."""
        from lfx.custom.hash_validator import is_code_hash_allowed

        # Empty code should be allowed by hash validator
        assert is_code_hash_allowed("") is True
        assert is_code_hash_allowed("   ") is True


# Made with Bob

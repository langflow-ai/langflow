import pytest

from langflow.components.google import GoogleOAuthToken
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestGoogleOAuthTokenComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return GoogleOAuthToken

    @pytest.fixture
    def default_kwargs(self):
        return {
            "scopes": "https://www.googleapis.com/auth/userinfo.email",
            "oauth_credentials": "path/to/credentials.json",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "oauth", "file_name": "GoogleOAuthToken"},
        ]

    def test_validate_scopes_valid(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.validate_scopes("https://www.googleapis.com/auth/userinfo.email")
        # No exception should be raised

    def test_validate_scopes_invalid(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Invalid scope format."):
            component.validate_scopes("invalid_scope")

    async def test_build_output(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        result = await component.build_output()
        assert result is not None
        assert isinstance(result.data, dict)
        assert "access_token" in result.data  # Assuming access_token is part of the returned data

    async def test_build_output_missing_credentials(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, {**default_kwargs, "oauth_credentials": None})
        with pytest.raises(ValueError, match="OAuth 2.0 Credentials file not provided."):
            await component.build_output()

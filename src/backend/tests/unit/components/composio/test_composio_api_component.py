import pytest
from langflow.components.composio import ComposioAPIComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestComposioAPIComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ComposioAPIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "entity_id": "default_entity",
            "api_key": "test_api_key",
            "app_names": "test_app",
            "app_credentials": "test_credentials",
            "username": "test_user",
            "action_names": ["test_action"],
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "composio_api", "file_name": "ComposioAPI"},
        ]

    async def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tools = component.build_tool()
        assert tools is not None
        assert isinstance(tools, list)

    async def test_check_for_authorization_connected(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        status = component._check_for_authorization(app="test_app")
        assert "CONNECTED" in status

    async def test_get_oauth_apps(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        oauth_apps = component._get_oauth_apps(api_key="test_api_key")
        assert isinstance(oauth_apps, list)

    async def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {
            "app_names": {"options": [], "value": ""},
            "auth_status": {"show": False, "value": ""},
            "action_names": {"options": [], "value": []},
        }
        updated_config = component.update_build_config(build_config, field_value="test_app", field_name="app_names")
        assert updated_config["auth_status"]["show"] is True
        assert updated_config["action_names"]["show"] is False

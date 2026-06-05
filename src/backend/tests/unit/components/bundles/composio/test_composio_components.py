"""Unit tests for Composio components cloud validation."""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from lfx.base.composio.composio_base import ComposioBaseComponent
from lfx.components.composio.composio_api import ComposioAPIComponent


@pytest.mark.unit
class TestComposioCloudValidation:
    """Test Composio components cloud validation."""

    def test_composio_api_disabled_in_astra_cloud(self):
        """Test that ComposioAPI build_tool raises error in Astra Cloud."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "true"}):
            component = ComposioAPIComponent(api_key="test-key")

            with pytest.raises(ValueError, match=r".*") as exc_info:
                component.build_tool()

            error_msg = str(exc_info.value).lower()
            assert "astra" in error_msg or "cloud" in error_msg


@pytest.mark.unit
class TestComposioAuthScopes:
    """Test Composio auth scope configuration."""

    @pytest.fixture
    def gmail_schema(self):
        return {
            "composio_managed_auth_schemes": ["OAUTH2"],
            "auth_config_details": [
                {
                    "mode": "OAUTH2",
                    "fields": {
                        "auth_config_creation": {
                            "required": [
                                {"name": "client_id", "display_name": "Client ID", "required": True},
                                {"name": "client_secret", "display_name": "Client Secret", "required": True},
                            ],
                            "optional": [
                                {
                                    "name": "scopes",
                                    "display_name": "Scopes",
                                    "description": "Scopes to request from the user, comma separated",
                                    "default": "scope1,scope2",
                                    "required": False,
                                }
                            ],
                        }
                    },
                }
            ],
        }

    def test_render_scopes_field_uses_default_scopes(self, gmail_schema):
        component = ComposioBaseComponent(api_key="test-key")
        build_config = {
            "scopes": {"name": "scopes", "value": "", "show": False, "required": False},
            "action_button": {"name": "action_button"},
        }

        component._render_scopes_field(build_config, gmail_schema, "Composio_Managed")

        assert build_config["scopes"]["show"] is True
        assert build_config["scopes"]["advanced"] is True
        assert build_config["scopes"]["value"] == "scope1,scope2"
        assert "comma separated" in build_config["scopes"]["info"]

    def test_auth_config_credentials_use_edited_scopes(self, gmail_schema):
        component = ComposioBaseComponent(api_key="test-key")
        build_config = {"scopes": {"value": " scope1, scope2 ,, scope3 "}}

        credentials = component._get_auth_config_credentials(build_config, gmail_schema, "Composio_Managed")

        assert credentials == {"scopes": "scope1,scope2,scope3"}

    def test_create_new_auth_config_passes_scope_credentials(self):
        component = ComposioBaseComponent(api_key="test-key")
        composio = MagicMock()
        composio.auth_configs.create.return_value = SimpleNamespace(id="auth-config-id")
        component._build_wrapper = MagicMock(return_value=composio)

        auth_config_id = component.create_new_auth_config("gmail", credentials={"scopes": "scope1,scope2"})

        assert auth_config_id == "auth-config-id"
        composio.auth_configs.create.assert_called_once_with(
            toolkit="gmail",
            options={"type": "use_composio_managed_auth", "credentials": {"scopes": "scope1,scope2"}},
        )

    def test_user_id_options_are_populated_from_connected_accounts(self):
        component = ComposioBaseComponent(api_key="test-key", entity_id="default")
        component.app_name = "gmail"
        composio = MagicMock()
        composio.connected_accounts.list.return_value = SimpleNamespace(
            items=[
                SimpleNamespace(
                    user_id="gmail-work",
                    status="ACTIVE",
                    auth_config=SimpleNamespace(auth_scheme="OAUTH2"),
                ),
                SimpleNamespace(
                    user_id="gmail-personal",
                    status="INITIATED",
                    auth_config=SimpleNamespace(auth_scheme="OAUTH2"),
                ),
            ]
        )
        component._build_wrapper = MagicMock(return_value=composio)
        build_config = {"entity_id": {"value": "default", "show": True}}

        component._update_user_id_options(build_config)

        assert build_config["entity_id"]["options"] == ["default", "gmail-personal", "gmail-work"]
        assert build_config["entity_id"]["combobox"] is True
        assert build_config["entity_id"]["options_metadata"][1]["status"] == "INITIATED"
        assert build_config["entity_id"]["options_metadata"][2]["status"] == "ACTIVE"
        composio.connected_accounts.list.assert_called_once_with(toolkit_slugs=["gmail"], limit=1000)

    def test_user_id_change_clears_stale_connection_state(self, gmail_schema):
        component = ComposioBaseComponent(api_key="test-key", entity_id="default")
        component.app_name = "gmail"
        component._actions_data = {"GMAIL_TEST": {"display_name": "Test", "action_fields": []}}
        component._action_schemas = {}
        component._get_toolkit_schema = MagicMock(return_value=gmail_schema)
        component._update_user_id_options = MagicMock()
        component._find_active_connection_for_app = MagicMock(return_value=None)

        build_config = {
            "entity_id": {"value": "default", "show": True},
            "auth_mode": {"value": "Composio_Managed", "show": True},
            "auth_link": {
                "value": "validated",
                "connection_id": "old-connection-id",
                "auth_config_id": "old-auth-config-id",
                "auth_scheme": "OAUTH2",
                "start_fresh": True,
            },
            "action_button": {"options": [], "helper_text": "", "helper_text_metadata": {}, "show": True},
        }

        updated_config = component.update_build_config(build_config, "gmail-work", "entity_id")

        assert component.entity_id == "gmail-work"
        assert updated_config["auth_link"]["value"] == "connect"
        assert "connection_id" not in updated_config["auth_link"]
        assert "auth_config_id" not in updated_config["auth_link"]
        assert "auth_scheme" not in updated_config["auth_link"]
        assert "start_fresh" not in updated_config["auth_link"]
        assert updated_config["action_button"]["helper_text"] == "Please connect before selecting actions."

    def test_start_fresh_resets_workflow_without_creating_link(self, gmail_schema):
        component = ComposioBaseComponent(api_key="test-key", entity_id="default")
        component.app_name = "gmail"
        component._actions_data = {"GMAIL_TEST": {"display_name": "Test", "action_fields": []}}
        component._action_schemas = {}

        composio = MagicMock()
        component._build_wrapper = MagicMock(return_value=composio)
        component._get_toolkit_schema = MagicMock(return_value=gmail_schema)
        component._find_active_connection_for_app = MagicMock(return_value=("old-connection-id", "ACTIVE"))

        build_config = {
            "entity_id": {"value": "default", "show": True},
            "api_key": {"value": "test-key", "show": True},
            "auth_mode": {"value": "Composio_Managed", "options": ["Composio_Managed"], "show": True},
            "auth_link": {"value": "validated", "connection_id": "old-connection-id", "show": False},
            "start_fresh_connection": {"value": [{"name": "Start Fresh", "metadata": "start_fresh"}], "show": True},
            "action_button": {"options": [], "helper_text": "", "helper_text_metadata": {}, "show": True},
            "scopes": {"value": "scope1,scope2", "show": True},
        }

        updated_config = component.update_build_config(
            build_config,
            [{"name": "Start Fresh", "metadata": "start_fresh"}],
            "start_fresh_connection",
        )

        assert updated_config["auth_link"]["value"] == "connect"
        assert "connection_id" not in updated_config["auth_link"]
        assert updated_config["auth_link"]["start_fresh"] is True
        assert updated_config["auth_mode"]["show"] is True
        assert updated_config["auth_mode"]["options"] == ["Composio_Managed", "OAUTH2"]
        assert updated_config["auth_mode"].get("value") in (None, "")
        assert updated_config["scopes"]["show"] is False
        assert updated_config["action_button"]["helper_text"] == "Please connect before selecting actions."
        composio.auth_configs.create.assert_not_called()
        composio.connected_accounts.link.assert_not_called()
        component._find_active_connection_for_app.assert_not_called()

    def test_start_fresh_auth_mode_selection_does_not_reuse_active_connection(self, gmail_schema):
        component = ComposioBaseComponent(api_key="test-key", entity_id="default")
        component.app_name = "gmail"
        component._actions_data = {"GMAIL_TEST": {"display_name": "Test", "action_fields": []}}
        component._action_schemas = {}
        component._get_toolkit_schema = MagicMock(return_value=gmail_schema)
        component._find_active_connection_for_app = MagicMock(return_value=("old-connection-id", "ACTIVE"))

        build_config = {
            "auth_mode": {"value": "", "options": ["Composio_Managed", "OAUTH2"], "show": True},
            "auth_link": {"value": "connect", "start_fresh": True, "show": False},
            "create_auth_config": {},
            "action_button": {"options": [], "helper_text": "", "helper_text_metadata": {}, "show": True},
            "scopes": {"value": "", "show": False, "required": False},
        }

        updated_config = component.update_build_config(build_config, "Composio_Managed", "auth_mode")

        assert updated_config["auth_link"]["value"] == "connect"
        assert updated_config["auth_link"]["start_fresh"] is True
        assert "connection_id" not in updated_config["auth_link"]
        assert updated_config["scopes"]["show"] is True
        assert updated_config["scopes"]["value"] == "scope1,scope2"
        component._find_active_connection_for_app.assert_not_called()

    def test_start_fresh_connect_creates_new_link_after_auth_mode_selection(self, gmail_schema):
        component = ComposioBaseComponent(api_key="test-key", entity_id="default")
        component.app_name = "gmail"
        component._actions_data = {"GMAIL_TEST": {"display_name": "Test", "action_fields": []}}
        component._action_schemas = {}

        composio = MagicMock()
        composio.auth_configs.create.return_value = SimpleNamespace(id="new-auth-config-id")
        composio.connected_accounts.link.return_value = SimpleNamespace(
            redirect_url="https://connect.composio.dev/new", id="new-connection-id"
        )
        component._build_wrapper = MagicMock(return_value=composio)
        component._get_toolkit_schema = MagicMock(return_value=gmail_schema)
        component._find_active_connection_for_app = MagicMock(return_value=("old-connection-id", "ACTIVE"))

        build_config = {
            "auth_mode": {"value": "Composio_Managed", "options": ["Composio_Managed", "OAUTH2"], "show": True},
            "auth_link": {"value": "connect", "start_fresh": True, "show": False},
            "start_fresh_connection": {"value": "disabled", "show": True},
            "action_button": {"options": [], "helper_text": "", "helper_text_metadata": {}, "show": True},
            "scopes": {"value": "scope1,scope2", "show": True},
        }

        updated_config = component.update_build_config(build_config, {"connect": True}, "auth_link")

        assert updated_config["auth_link"]["value"] == "https://connect.composio.dev/new"
        assert updated_config["auth_link"]["connection_id"] == "new-connection-id"
        assert "start_fresh" not in updated_config["auth_link"]
        composio.auth_configs.create.assert_called_once_with(
            toolkit="gmail",
            options={"type": "use_composio_managed_auth", "credentials": {"scopes": "scope1,scope2"}},
        )
        composio.connected_accounts.link.assert_called_once_with(user_id="default", auth_config_id="new-auth-config-id")
        component._find_active_connection_for_app.assert_not_called()

    def test_start_fresh_pending_refresh_does_not_restore_active_connection(self, gmail_schema):
        component = ComposioBaseComponent(api_key="test-key", entity_id="default")
        component.app_name = "gmail"
        component._actions_data = {"GMAIL_TEST": {"display_name": "Test", "action_fields": []}}
        component._action_schemas = {}
        component._get_toolkit_schema = MagicMock(return_value=gmail_schema)
        component._find_active_connection_for_app = MagicMock(return_value=("old-connection-id", "ACTIVE"))

        build_config = {
            "auth_mode": {"value": "", "options": ["Composio_Managed", "OAUTH2"], "show": True},
            "auth_link": {"value": "connect", "start_fresh": True, "show": False},
            "start_fresh_connection": {"value": "disabled", "show": True},
            "action_button": {"options": [], "helper_text": "", "helper_text_metadata": {}, "show": True},
            "scopes": {"value": "", "show": False},
        }

        updated_config = component.update_build_config(build_config, None, None)

        assert updated_config["auth_link"]["value"] == "connect"
        assert updated_config["auth_link"]["start_fresh"] is True
        assert "connection_id" not in updated_config["auth_link"]
        assert updated_config["auth_mode"]["show"] is True
        assert updated_config["auth_mode"].get("value") in (None, "")
        component._find_active_connection_for_app.assert_not_called()

    def test_composio_base_execute_disabled_in_astra_cloud(self):
        """Test that ComposioBase execute_action raises error in Astra Cloud."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "false"}):
            component = ComposioBaseComponent(api_key="test-key")

        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "true"}):
            with pytest.raises(ValueError, match=r".*") as exc_info:
                component.execute_action()

            error_msg = str(exc_info.value).lower()
            assert "astra" in error_msg or "cloud" in error_msg

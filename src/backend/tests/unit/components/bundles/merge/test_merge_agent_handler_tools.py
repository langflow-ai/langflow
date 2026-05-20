"""Unit tests for Merge Agent Handler bundle utilities."""

import pytest
from lfx.components.merge.merge_agent_handler_tool import MergeAgentHandlerToolsComponent
from lfx.components.merge.schema_utils import create_dispatch_schema
from pydantic import ValidationError


class _FakeValidationError:
    def errors(self):
        return [
            {"type": "missing", "loc": ("input", "cursor")},
            {"type": "missing", "loc": ("input", "id")},
        ]


class _FakeMergeAgentHandlerClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def get_tool_packs(self):
        return [
            {
                "id": "tp_1234567890ab",
                "name": "HR Pack",
                "connectors": [{"name": "Greenhouse", "slug": "greenhouse"}],
            }
        ]

    def get_registered_users(self, *, is_test=None):
        if is_test:
            return [
                {
                    "id": "ru_1234567890ab",
                    "origin_user_name": "Taylor",
                    "authenticated_connectors": ["greenhouse"],
                }
            ]
        return []

    def list_mcp_tools(self, tool_pack_id, user_id):
        assert tool_pack_id == "tp_1234567890ab"
        assert user_id == "ru_1234567890ab"
        return [
            {
                "name": "gong_list_users",
                "description": "List users from Gong.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cursor": {"type": "string"},
                    },
                    "required": ["cursor"],
                },
            }
        ]

    def call_mcp_tool(self, _tool_pack_id, _user_id, name, args):
        return f"called {name} with {args}"


@pytest.mark.unit
class TestMergeAgentHandlerToolsComponent:
    """Tests for Merge Agent Handler tool helper behavior."""

    def test_tool_pack_option_map_includes_connectors(self):
        packs = [
            {
                "id": "tp_1234567890ab",
                "name": "HR Pack",
                "connectors": [{"name": "Greenhouse", "slug": "greenhouse"}, {"slug": "workday"}],
            }
        ]

        option_map = MergeAgentHandlerToolsComponent._tool_pack_option_map(packs)

        assert len(option_map) == 1
        label = next(iter(option_map.keys()))
        assert "HR Pack" in label
        assert "Apps:" in label
        assert "Greenhouse" in label
        assert "workday" in label
        assert option_map[label] == "tp_1234567890ab"

    def test_registered_user_option_map_includes_authenticated_connectors(self):
        users = [
            {
                "id": "ru_1234567890ab",
                "origin_user_name": "Taylor",
                "authenticated_connectors": ["salesforce", "jira", "salesforce"],
            }
        ]

        option_map = MergeAgentHandlerToolsComponent._registered_user_option_map(users)

        assert len(option_map) == 1
        label = next(iter(option_map.keys()))
        assert "Taylor" in label
        assert "Connected:" in label
        assert "salesforce" in label
        assert "jira" in label
        assert option_map[label] == "ru_1234567890ab"

    def test_validation_error_message_lists_missing_fields(self):
        message = MergeAgentHandlerToolsComponent._handle_tool_validation_error(_FakeValidationError())

        assert "Missing required fields" in message
        assert "input.cursor" in message
        assert "input.id" in message

    def test_environment_options_are_capitalized(self):
        environment_input = next(
            input_ for input_ in MergeAgentHandlerToolsComponent.inputs if input_.name == "environment"
        )

        assert set(environment_input.options) == {"Production", "Test"}

    def test_tool_pack_option_map_avoids_label_collisions(self):
        packs = [
            {
                "id": "tp_12345678aaaa",
                "name": "Finance Pack",
                "connectors": [{"name": "NetSuite"}],
            },
            {
                "id": "tp_12345678bbbb",
                "name": "Finance Pack",
                "connectors": [{"name": "NetSuite"}],
            },
        ]

        option_map = MergeAgentHandlerToolsComponent._tool_pack_option_map(packs)

        assert len(option_map) == 2
        assert set(option_map.values()) == {"tp_12345678aaaa", "tp_12345678bbbb"}
        assert any("[tp_12345678bbbb]" in label for label in option_map)

    def test_registered_user_option_map_avoids_label_collisions(self):
        users = [
            {
                "id": "ru_12345678aaaa",
                "origin_user_name": "Alex",
                "authenticated_connectors": ["salesforce"],
            },
            {
                "id": "ru_12345678bbbb",
                "origin_user_name": "Alex",
                "authenticated_connectors": ["salesforce"],
            },
        ]

        option_map = MergeAgentHandlerToolsComponent._registered_user_option_map(users)

        assert len(option_map) == 2
        assert set(option_map.values()) == {"ru_12345678aaaa", "ru_12345678bbbb"}
        assert any("[ru_12345678bbbb]" in label for label in option_map)

    def test_dispatch_schema_constrains_tool_name(self):
        schema = create_dispatch_schema(["gong_list_users", "gong_get_user"])

        model = schema(tool_name="gong_list_users", arguments={"cursor": "abc"})
        assert model.tool_name == "gong_list_users"

        with pytest.raises(ValidationError):
            schema(tool_name="invalid_tool", arguments={})

    def test_update_build_config_populates_options(self, monkeypatch):
        monkeypatch.setattr(
            "lfx.components.merge.merge_agent_handler_tool.MergeAgentHandlerClient",
            _FakeMergeAgentHandlerClient,
        )
        component = MergeAgentHandlerToolsComponent(
            api_key="placeholder",  # pragma: allowlist secret
            tool_pack_id="",
            environment="Test",
            registered_user_id="",
            _session_id="test-session",
        )
        build_config = component.to_frontend_node()["data"]["node"]["template"]

        updated = component.update_build_config(
            build_config=build_config,
            field_value="placeholder",  # pragma: allowlist secret
            field_name="api_key",
        )

        assert updated["tool_pack_id"]["options"]
        assert updated["registered_user_id"]["options"]
        assert "HR Pack" in updated["tool_pack_id"]["options"][0]
        assert "Taylor" in updated["registered_user_id"]["options"][0]

    def test_build_tool_requires_tool_pack_and_registered_user(self):
        component = MergeAgentHandlerToolsComponent(
            api_key="placeholder",  # pragma: allowlist secret
            tool_pack_id="",
            environment="Test",
            registered_user_id="",
            _session_id="test-session",
        )

        with pytest.raises(ValueError, match="Tool Pack and Registered User must be selected"):
            component.build_tool()

    def test_build_tool_validation_error_is_user_friendly(self, monkeypatch):
        monkeypatch.setattr(
            "lfx.components.merge.merge_agent_handler_tool.MergeAgentHandlerClient",
            _FakeMergeAgentHandlerClient,
        )
        component = MergeAgentHandlerToolsComponent(
            api_key="placeholder",  # pragma: allowlist secret
            tool_pack_id="tp_1234567890ab",
            environment="Test",
            registered_user_id="ru_1234567890ab",
            _session_id="test-session",
        )

        tools = component.build_tool()
        assert len(tools) == 1

        result = tools[0].invoke({})
        assert "Missing required fields" in result
        assert "cursor" in result

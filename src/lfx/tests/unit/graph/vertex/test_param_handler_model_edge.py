"""Tests for skipping load_from_db credential fields when model has incoming edge.

When a model component is connected via wire to a node's model input,
the connected component provides its own credentials. The node's own
secret fields (like api_key) should NOT be resolved from the database,
preventing errors like 'OPENAI_API_KEY variable not found'.
"""

from unittest.mock import MagicMock

from lfx.graph.vertex.param_handler import ParameterHandler


class TestSkipLoadFromDbWhenModelHasEdge:
    """Tests for _process_direct_type_field skipping load_from_db for secrets when model has edge."""

    def _create_handler_with_template(self, template: dict, *, model_has_edge: bool = False) -> ParameterHandler:
        """Create a ParameterHandler with the given template and optional model edge."""
        mock_vertex = MagicMock()
        mock_vertex.data = {"node": {"template": template}}

        def mock_get_incoming_edge(field_name: str):
            if field_name == "model" and model_has_edge:
                return "source-node-id"
            return None

        mock_vertex.get_incoming_edge_by_target_param = MagicMock(side_effect=mock_get_incoming_edge)
        return ParameterHandler(mock_vertex, storage_service=None)

    def test_should_add_secret_to_load_from_db_when_no_model_edge(self):
        """Secret fields should be resolved normally when model has no wire."""
        # Arrange
        template = {
            "model": {"type": "model", "value": None, "show": True},
            "api_key": {
                "type": "str",
                "_input_type": "SecretStrInput",
                "password": True,
                "load_from_db": True,
                "value": "OPENAI_API_KEY",
                "show": True,
            },
        }
        handler = self._create_handler_with_template(template, model_has_edge=False)

        # Act
        load_from_db_fields: list[str] = []
        params: dict = {}
        handler._process_direct_type_field("api_key", template["api_key"], params, load_from_db_fields)

        # Assert
        assert "api_key" in load_from_db_fields

    def test_should_skip_secret_load_from_db_when_model_has_edge(self):
        """Secret fields should NOT be resolved when model has a connected wire."""
        # Arrange
        template = {
            "model": {"type": "model", "value": None, "show": True},
            "api_key": {
                "type": "str",
                "_input_type": "SecretStrInput",
                "password": True,
                "load_from_db": True,
                "value": "OPENAI_API_KEY",
                "show": True,
            },
        }
        handler = self._create_handler_with_template(template, model_has_edge=True)

        # Act
        load_from_db_fields: list[str] = []
        params: dict = {}
        handler._process_direct_type_field("api_key", template["api_key"], params, load_from_db_fields)

        # Assert
        assert "api_key" not in load_from_db_fields

    def test_should_skip_password_field_when_model_has_edge(self):
        """Any password field should be skipped when model has edge, not just SecretStrInput."""
        # Arrange
        template = {
            "model": {"type": "model", "value": None, "show": True},
            "custom_token": {
                "type": "str",
                "password": True,
                "load_from_db": True,
                "value": "MY_CUSTOM_TOKEN",
                "show": True,
            },
        }
        handler = self._create_handler_with_template(template, model_has_edge=True)

        # Act
        load_from_db_fields: list[str] = []
        params: dict = {}
        handler._process_direct_type_field("custom_token", template["custom_token"], params, load_from_db_fields)

        # Assert
        assert "custom_token" not in load_from_db_fields

    def test_should_not_skip_non_secret_field_when_model_has_edge(self):
        """Non-secret fields with load_from_db should still be resolved even with model edge."""
        # Arrange
        template = {
            "model": {"type": "model", "value": None, "show": True},
            "system_prompt": {
                "type": "str",
                "load_from_db": True,
                "value": "MY_PROMPT_VAR",
                "show": True,
            },
        }
        handler = self._create_handler_with_template(template, model_has_edge=True)

        # Act
        load_from_db_fields: list[str] = []
        params: dict = {}
        handler._process_direct_type_field("system_prompt", template["system_prompt"], params, load_from_db_fields)

        # Assert
        assert "system_prompt" in load_from_db_fields

    def test_should_skip_field_with_direct_incoming_edge(self):
        """Fields with their own incoming edge should be skipped regardless of model edge."""
        # Arrange
        template = {
            "some_field": {
                "type": "str",
                "load_from_db": True,
                "value": "SOME_VAR",
                "show": True,
            },
        }
        mock_vertex = MagicMock()
        mock_vertex.data = {"node": {"template": template}}
        mock_vertex.get_incoming_edge_by_target_param = MagicMock(return_value="source-node")
        handler = ParameterHandler(mock_vertex, storage_service=None)

        # Act
        load_from_db_fields: list[str] = []
        params: dict = {}
        handler._process_direct_type_field("some_field", template["some_field"], params, load_from_db_fields)

        # Assert
        assert "some_field" not in load_from_db_fields

    def test_should_not_skip_when_no_model_field_in_template(self):
        """Components without a model field should resolve secrets normally."""
        # Arrange
        template = {
            "api_key": {
                "type": "str",
                "_input_type": "SecretStrInput",
                "password": True,
                "load_from_db": True,
                "value": "OPENAI_API_KEY",
                "show": True,
            },
        }
        mock_vertex = MagicMock()
        mock_vertex.data = {"node": {"template": template}}
        mock_vertex.get_incoming_edge_by_target_param = MagicMock(return_value=None)
        handler = ParameterHandler(mock_vertex, storage_service=None)

        # Act
        load_from_db_fields: list[str] = []
        params: dict = {}
        handler._process_direct_type_field("api_key", template["api_key"], params, load_from_db_fields)

        # Assert
        assert "api_key" in load_from_db_fields

    def test_should_not_affect_fields_without_load_from_db(self):
        """Fields without load_from_db should never be added regardless of edges."""
        # Arrange
        template = {
            "model": {"type": "model", "value": None, "show": True},
            "description": {
                "type": "str",
                "value": "Some description",
                "show": True,
            },
        }
        handler = self._create_handler_with_template(template, model_has_edge=True)

        # Act
        load_from_db_fields: list[str] = []
        params: dict = {}
        handler._process_direct_type_field("description", template["description"], params, load_from_db_fields)

        # Assert
        assert "description" not in load_from_db_fields

    def test_should_skip_secret_load_from_db_when_connection_mode_active(self):
        """Secret fields must NOT be resolved via load_from_db in connection mode.

        When the model field has _connection_mode: true (user chose
        'Connect other models'), credential fields should be skipped.
        """
        # Arrange
        template = {
            "model": {
                "type": "model",
                "value": [],
                "show": True,
                "_connection_mode": True,
            },
            "api_key": {
                "type": "str",
                "_input_type": "SecretStrInput",
                "password": True,
                "load_from_db": True,
                "value": "",
                "show": True,
            },
        }
        handler = self._create_handler_with_template(template, model_has_edge=False)

        # Act
        load_from_db_fields: list[str] = []
        params: dict = {}
        handler._process_direct_type_field("api_key", template["api_key"], params, load_from_db_fields)

        # Assert — api_key must NOT be in load_from_db_fields
        assert "api_key" not in load_from_db_fields

    def test_should_allow_secret_load_from_db_when_connection_mode_false(self):
        """Secret fields should be resolved normally when _connection_mode is false."""
        # Arrange
        template = {
            "model": {
                "type": "model",
                "value": [{"name": "gpt-4", "provider": "OpenAI"}],
                "show": True,
                "_connection_mode": False,
            },
            "api_key": {
                "type": "str",
                "_input_type": "SecretStrInput",
                "password": True,
                "load_from_db": True,
                "value": "OPENAI_API_KEY",
                "show": True,
            },
        }
        handler = self._create_handler_with_template(template, model_has_edge=False)

        # Act
        load_from_db_fields: list[str] = []
        params: dict = {}
        handler._process_direct_type_field("api_key", template["api_key"], params, load_from_db_fields)

        # Assert — api_key SHOULD be in load_from_db_fields
        assert "api_key" in load_from_db_fields

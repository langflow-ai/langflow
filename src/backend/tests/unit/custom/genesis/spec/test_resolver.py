"""Tests for Genesis Spec Variable Resolver."""

import pytest
from langflow.custom.genesis.spec.resolver import VariableResolver
from langflow.custom.genesis.spec.models import AgentSpec, Variable


class TestVariableResolver:
    """Test VariableResolver class."""

    @pytest.fixture
    def resolver(self):
        """Create VariableResolver instance."""
        return VariableResolver()

    @pytest.fixture
    def spec_with_variables(self):
        """Agent spec with variables."""
        return AgentSpec(
            id="test-agent",
            name="Test Agent",
            description="Agent with variables",
            components=[
                {
                    "id": "agent-main",
                    "name": "Main Agent",
                    "kind": "Agent",
                    "type": "genesis:agent",
                    "config": {
                        "api_key": "{{api_key}}",
                        "temperature": "{{temperature}}",
                        "model": "{{model_name}}"
                    }
                }
            ],
            variables=[
                Variable(
                    name="api_key",
                    type="string",
                    required=True,
                    description="API key for external service"
                ),
                Variable(
                    name="temperature",
                    type="float",
                    required=False,
                    default=0.7,
                    description="Model temperature"
                ),
                Variable(
                    name="model_name",
                    type="string",
                    required=False,
                    default="gpt-3.5-turbo",
                    description="Model name"
                )
            ]
        )

    def test_resolver_initialization(self, resolver):
        """Test VariableResolver initialization."""
        assert resolver is not None

    def test_resolve_variables_with_all_values(self, resolver, spec_with_variables):
        """Test resolving variables when all values are provided."""
        runtime_vars = {
            "api_key": "sk-test123",
            "temperature": 0.9,
            "model_name": "gpt-4"
        }

        resolved_spec = resolver.resolve_variables(spec_with_variables, runtime_vars)

        # Check that variables were resolved in component config
        agent_config = resolved_spec.components[0].config
        assert agent_config["api_key"] == "sk-test123"
        assert agent_config["temperature"] == 0.9
        assert agent_config["model"] == "gpt-4"

    def test_resolve_variables_with_defaults(self, resolver, spec_with_variables):
        """Test resolving variables using default values."""
        runtime_vars = {
            "api_key": "sk-test123"
            # temperature and model_name will use defaults
        }

        resolved_spec = resolver.resolve_variables(spec_with_variables, runtime_vars)

        agent_config = resolved_spec.components[0].config
        assert agent_config["api_key"] == "sk-test123"
        assert agent_config["temperature"] == 0.7  # Default value
        assert agent_config["model"] == "gpt-3.5-turbo"  # Default value

    def test_resolve_variables_missing_required(self, resolver, spec_with_variables):
        """Test error when required variable is missing."""
        runtime_vars = {
            "temperature": 0.8
            # Missing required api_key
        }

        with pytest.raises(ValueError) as exc_info:
            resolver.resolve_variables(spec_with_variables, runtime_vars)

        assert "Required variable 'api_key' not provided" in str(exc_info.value)

    def test_resolve_variables_no_variables_defined(self, resolver):
        """Test resolving when no variables are defined in spec."""
        spec = AgentSpec(
            id="simple-agent",
            name="Simple Agent",
            description="Agent without variables",
            components=[
                {
                    "id": "agent-main",
                    "name": "Main Agent",
                    "kind": "Agent",
                    "type": "genesis:agent",
                    "config": {"model": "gpt-3.5-turbo"}
                }
            ]
        )

        runtime_vars = {"unused_var": "value"}
        resolved_spec = resolver.resolve_variables(spec, runtime_vars)

        # Should return original spec unchanged
        assert resolved_spec.components[0].config["model"] == "gpt-3.5-turbo"

    def test_resolve_variables_no_templates_in_config(self, resolver):
        """Test resolving when config has no variable templates."""
        spec = AgentSpec(
            id="static-agent",
            name="Static Agent",
            description="Agent with static config",
            components=[
                {
                    "id": "agent-main",
                    "name": "Main Agent",
                    "kind": "Agent",
                    "type": "genesis:agent",
                    "config": {"model": "gpt-3.5-turbo", "temperature": 0.7}
                }
            ],
            variables=[
                Variable(name="api_key", type="string", required=False, default="default-key")
            ]
        )

        runtime_vars = {"api_key": "runtime-key"}
        resolved_spec = resolver.resolve_variables(spec, runtime_vars)

        # Config should remain unchanged as no templates present
        agent_config = resolved_spec.components[0].config
        assert agent_config["model"] == "gpt-3.5-turbo"
        assert agent_config["temperature"] == 0.7

    def test_resolve_nested_variable_templates(self, resolver):
        """Test resolving variables in nested configurations."""
        spec = AgentSpec(
            id="nested-agent",
            name="Nested Agent",
            description="Agent with nested config",
            components=[
                {
                    "id": "complex-component",
                    "name": "Complex Component",
                    "kind": "Tool",
                    "type": "genesis:tool",
                    "config": {
                        "connection": {
                            "host": "{{db_host}}",
                            "port": "{{db_port}}",
                            "credentials": {
                                "username": "{{db_user}}",
                                "password": "{{db_password}}"
                            }
                        },
                        "settings": {
                            "timeout": "{{timeout}}",
                            "retries": "{{retries}}"
                        }
                    }
                }
            ],
            variables=[
                Variable(name="db_host", type="string", required=True),
                Variable(name="db_port", type="integer", default=5432),
                Variable(name="db_user", type="string", required=True),
                Variable(name="db_password", type="string", required=True),
                Variable(name="timeout", type="integer", default=30),
                Variable(name="retries", type="integer", default=3)
            ]
        )

        runtime_vars = {
            "db_host": "localhost",
            "db_user": "admin",
            "db_password": "secret123",
            "timeout": 60
            # db_port and retries will use defaults
        }

        resolved_spec = resolver.resolve_variables(spec, runtime_vars)

        config = resolved_spec.components[0].config
        assert config["connection"]["host"] == "localhost"
        assert config["connection"]["port"] == 5432  # Default
        assert config["connection"]["credentials"]["username"] == "admin"
        assert config["connection"]["credentials"]["password"] == "secret123"
        assert config["settings"]["timeout"] == 60
        assert config["settings"]["retries"] == 3  # Default

    def test_resolve_multiple_templates_in_single_value(self, resolver):
        """Test resolving multiple variable templates in a single config value."""
        spec = AgentSpec(
            id="multi-template-agent",
            name="Multi Template Agent",
            description="Agent with multiple templates in values",
            components=[
                {
                    "id": "component",
                    "name": "Component",
                    "kind": "Tool",
                    "type": "genesis:tool",
                    "config": {
                        "url": "https://{{host}}:{{port}}/{{path}}",
                        "message": "Hello {{user}}, your API key is {{api_key}}"
                    }
                }
            ],
            variables=[
                Variable(name="host", type="string", default="localhost"),
                Variable(name="port", type="integer", default=8080),
                Variable(name="path", type="string", default="api/v1"),
                Variable(name="user", type="string", required=True),
                Variable(name="api_key", type="string", required=True)
            ]
        )

        runtime_vars = {
            "host": "api.example.com",
            "port": 443,
            "user": "john",
            "api_key": "sk-test123"
        }

        resolved_spec = resolver.resolve_variables(spec, runtime_vars)

        config = resolved_spec.components[0].config
        assert config["url"] == "https://api.example.com:443/api/v1"
        assert config["message"] == "Hello john, your API key is sk-test123"

    def test_resolve_variables_with_type_conversion(self, resolver):
        """Test that variables are converted to appropriate types."""
        spec = AgentSpec(
            id="typed-agent",
            name="Typed Agent",
            description="Agent with typed variables",
            components=[
                {
                    "id": "component",
                    "name": "Component",
                    "kind": "Tool",
                    "type": "genesis:tool",
                    "config": {
                        "count": "{{item_count}}",
                        "enabled": "{{is_enabled}}",
                        "rate": "{{success_rate}}"
                    }
                }
            ],
            variables=[
                Variable(name="item_count", type="integer", default=10),
                Variable(name="is_enabled", type="boolean", default=True),
                Variable(name="success_rate", type="float", default=0.95)
            ]
        )

        runtime_vars = {
            "item_count": "25",  # String that should be converted to int
            "is_enabled": "false",  # String that should be converted to bool
            "success_rate": "0.85"  # String that should be converted to float
        }

        resolved_spec = resolver.resolve_variables(spec, runtime_vars)

        config = resolved_spec.components[0].config
        assert config["count"] == 25
        assert isinstance(config["count"], int)
        assert config["enabled"] is False
        assert isinstance(config["enabled"], bool)
        assert config["rate"] == 0.85
        assert isinstance(config["rate"], float)

    def test_resolve_variables_preserve_non_template_values(self, resolver):
        """Test that non-template values are preserved unchanged."""
        spec = AgentSpec(
            id="mixed-agent",
            name="Mixed Agent",
            description="Agent with mixed template and static values",
            components=[
                {
                    "id": "component",
                    "name": "Component",
                    "kind": "Tool",
                    "type": "genesis:tool",
                    "config": {
                        "dynamic_value": "{{variable}}",
                        "static_string": "this is static",
                        "static_number": 42,
                        "static_bool": True,
                        "static_list": [1, 2, 3],
                        "static_dict": {"key": "value"}
                    }
                }
            ],
            variables=[
                Variable(name="variable", type="string", default="dynamic")
            ]
        )

        resolved_spec = resolver.resolve_variables(spec, {})

        config = resolved_spec.components[0].config
        assert config["dynamic_value"] == "dynamic"
        assert config["static_string"] == "this is static"
        assert config["static_number"] == 42
        assert config["static_bool"] is True
        assert config["static_list"] == [1, 2, 3]
        assert config["static_dict"] == {"key": "value"}

    def test_validate_variable_types(self, resolver):
        """Test variable type validation."""
        # Test valid types
        assert resolver._validate_and_convert_type("42", "integer") == 42
        assert resolver._validate_and_convert_type("3.14", "float") == 3.14
        assert resolver._validate_and_convert_type("true", "boolean") is True
        assert resolver._validate_and_convert_type("false", "boolean") is False
        assert resolver._validate_and_convert_type("hello", "string") == "hello"

        # Test invalid conversions
        with pytest.raises(ValueError):
            resolver._validate_and_convert_type("not_a_number", "integer")

        with pytest.raises(ValueError):
            resolver._validate_and_convert_type("not_a_float", "float")

    def test_extract_variables_from_template(self, resolver):
        """Test extracting variable names from template strings."""
        # Single variable
        variables = resolver._extract_variables_from_template("{{api_key}}")
        assert variables == ["api_key"]

        # Multiple variables
        variables = resolver._extract_variables_from_template("{{host}}:{{port}}")
        assert set(variables) == {"host", "port"}

        # No variables
        variables = resolver._extract_variables_from_template("static string")
        assert variables == []

        # Variables with spaces
        variables = resolver._extract_variables_from_template("{{ api_key }} and {{ port }}")
        assert set(variables) == {"api_key", "port"}
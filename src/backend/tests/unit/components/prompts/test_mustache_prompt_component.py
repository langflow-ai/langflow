import pytest
from langflow.components.prompts.mustache_prompt import MustachePromptComponent
from langflow.schema.message import Message

from tests.base import DID_NOT_EXIST, ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestMustachePromptComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return MustachePromptComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"template": "Hello {{name}}!", "name": "John", "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.19", "module": "prompts", "file_name": DID_NOT_EXIST},
            {"version": "1.1.0", "module": "prompts", "file_name": DID_NOT_EXIST},
            {"version": "1.1.1", "module": "prompts", "file_name": DID_NOT_EXIST},
        ]

    def test_post_code_processing(self, component_class, default_kwargs):
        """Test that post_code_processing correctly processes mustache variables."""
        component = component_class(**default_kwargs)
        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]

        # Check that the template value is set correctly
        assert node_data["template"]["template"]["value"] == "Hello {{name}}!"

        # Check that the mustache variable is detected and added to custom_fields
        assert "name" in node_data["custom_fields"]["template"]
        assert "name" in node_data["template"]
        assert node_data["template"]["name"]["value"] == "John"

    async def test_mustache_prompt_component_latest(self, component_class, default_kwargs):
        """Test that the component runs and returns a Message."""
        component = component_class(**default_kwargs)
        result = await component.build_prompt()
        assert result is not None
        assert isinstance(result, Message)

    async def test_build_prompt_basic(self, component_class):
        """Test basic mustache prompt building."""
        component = component_class(template="Hello {{name}}!", name="World")
        result = await component.build_prompt()

        assert isinstance(result, Message)
        assert result.text == "Hello World!"

    async def test_build_prompt_multiple_variables(self, component_class):
        """Test mustache prompt with multiple variables."""
        component = component_class(template="Hello {{name}}! You are {{age}} years old.", name="Alice", age="25")
        result = await component.build_prompt()

        assert isinstance(result, Message)
        assert result.text == "Hello Alice! You are 25 years old."

    async def test_build_prompt_missing_variable(self, component_class):
        """Test mustache prompt with missing variable."""
        component = component_class(template="Hello {{name}}! You are {{age}} years old.", name="Bob")
        result = await component.build_prompt()

        assert isinstance(result, Message)
        # Missing variables should be rendered as empty strings in mustache
        assert result.text == "Hello Bob! You are  years old."

    async def test_build_prompt_no_variables(self, component_class):
        """Test mustache prompt with no variables."""
        component = component_class(template="Hello World!")
        result = await component.build_prompt()

        assert isinstance(result, Message)
        assert result.text == "Hello World!"

    async def test_build_prompt_empty_template(self, component_class):
        """Test mustache prompt with empty template."""
        component = component_class(template="")
        result = await component.build_prompt()

        assert isinstance(result, Message)
        assert result.text == ""

    async def test_build_prompt_complex_mustache(self, component_class):
        """Test mustache prompt with complex mustache syntax."""
        component = component_class(
            template="{{#show_greeting}}Hello {{name}}!{{/show_greeting}} {{#show_age}}You are {{age}}.{{/show_age}}",
            name="Charlie",
            age="30",
            show_greeting=True,
            show_age=False,
        )
        result = await component.build_prompt()

        assert isinstance(result, Message)
        # Only greeting should show, age section should be hidden
        assert result.text == "Hello Charlie! "

    async def test_build_prompt_with_special_characters(self, component_class):
        """Test mustache prompt with special characters in variables."""
        component = component_class(
            template="Message: {{message}}", message="Hello! How are you? I'm fine. 100% ready!"
        )
        result = await component.build_prompt()

        assert isinstance(result, Message)
        assert result.text == "Message: Hello! How are you? I'm fine. 100% ready!"

    async def test_build_prompt_with_newlines(self, component_class):
        """Test mustache prompt with newlines in template and variables."""
        component = component_class(
            template="Line 1: {{line1}}\nLine 2: {{line2}}", line1="First line", line2="Second line"
        )
        result = await component.build_prompt()

        assert isinstance(result, Message)
        assert result.text == "Line 1: First line\nLine 2: Second line"

    def test_field_type_is_mustache_prompt(self, component_class):
        """Test that the component uses MUSTACHE_PROMPT field type."""
        component = component_class()
        template_input = component.inputs[0]  # First input should be template

        from langflow.inputs.input_mixin import FieldTypes

        assert template_input.field_type == FieldTypes.MUSTACHE_PROMPT

    def test_component_metadata(self, component_class):
        """Test component metadata is correctly set."""
        component = component_class()

        assert component.display_name == "Mustache Prompt"
        assert component.description == "Create a prompt template with dynamic variables."
        assert component.icon == "prompts"
        assert component.trace_type == "prompt"

    def test_component_inputs_and_outputs(self, component_class):
        """Test that component has correct inputs and outputs."""
        component = component_class()

        # Should have one input (template)
        assert len(component.inputs) == 1
        assert component.inputs[0].name == "template"
        assert component.inputs[0].display_name == "Template"

        # Should have one output (prompt)
        assert len(component.outputs) == 1
        assert component.outputs[0].name == "prompt"
        assert component.outputs[0].display_name == "Prompt Message"

    async def test_status_is_set_after_build(self, component_class):
        """Test that status is set to the prompt text after building."""
        component = component_class(template="Hello {{name}}!", name="Test")

        # Build the prompt
        result = await component.build_prompt()

        # Status should now be set to the prompt text
        assert component.status == "Hello Test!"
        assert isinstance(result, Message)
        assert result.text == "Hello Test!"

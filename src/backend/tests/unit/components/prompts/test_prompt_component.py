from langflow.components.prompts.Prompt import PromptComponent  # type: ignore


class TestPromptComponent:
    def test_post_code_processing(self):
        component = PromptComponent(template="Hello {name}!", name="John")
        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]
        assert node_data["template"]["template"]["value"] == "Hello {name}!"
        assert "name" in node_data["custom_fields"]["template"]
        assert "name" in node_data["template"]
        assert node_data["template"]["name"]["value"] == "John"

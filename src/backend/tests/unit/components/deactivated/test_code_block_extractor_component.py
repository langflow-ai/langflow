import pytest
from langflow.components.deactivated.code_block_extractor import CodeBlockExtractor
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCodeBlockExtractor(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CodeBlockExtractor

    @pytest.fixture
    def default_kwargs(self):
        return {
            "text": "Here is some code:\n```\ndef hello_world():\n    print('Hello, world!')\n```\nAnd some more text."
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "code_block_extractor", "file_name": "CodeBlockExtractor"},
        ]

    def test_get_code_block(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.get_code_block()
        assert result == "def hello_world():\n    print('Hello, world!')", "The extracted code block is incorrect."

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."

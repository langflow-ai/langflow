import pytest
from langflow.components.unstructured import UnstructuredComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestUnstructuredComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return UnstructuredComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "api_url": "https://api.unstructured.io",
            "chunking_strategy": "basic",
            "unstructured_args": {},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "unstructured", "file_name": "Unstructured"},
            {"version": "1.1.0", "module": "unstructured", "file_name": "unstructured"},
        ]

    def test_process_files_with_valid_files(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        file_list = [Mock(path="test_file.pdf"), Mock(path="test_file.docx")]
        result = component.process_files(file_list)
        assert result is not None
        assert len(result) == len(file_list)

    def test_process_files_with_no_files(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        file_list = []
        result = component.process_files(file_list)
        assert result == file_list

    def test_process_files_with_invalid_file_paths(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        file_list = [Mock(path=None)]
        result = component.process_files(file_list)
        assert result == file_list

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."

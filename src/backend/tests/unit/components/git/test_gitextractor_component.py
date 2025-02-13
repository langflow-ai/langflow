import pytest

from langflow.components.git import GitExtractorComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestGitExtractorComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return GitExtractorComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"repository_url": "https://github.com/username/repo"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "git_extractor", "file_name": "GitExtractor"},
        ]

    async def test_get_repository_info(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.get_repository_info()
        assert result is not None
        assert isinstance(result, list)
        assert "name" in result[0].data
        assert "url" in result[0].data

    async def test_get_statistics(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.get_statistics()
        assert result is not None
        assert isinstance(result, list)
        assert "total_files" in result[0].data
        assert "total_size_bytes" in result[0].data

    async def test_get_directory_structure(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.get_directory_structure()
        assert result is not None
        assert isinstance(result, Message)
        assert "Directory structure:" in result.text

    async def test_get_files_content(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.get_files_content()
        assert result is not None
        assert isinstance(result, list)
        assert all("path" in data.data for data in result)

    async def test_get_text_based_file_contents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.get_text_based_file_contents()
        assert result is not None
        assert isinstance(result, Message)
        assert "(Files content cropped to 300k characters" in result.text

import pytest
from langflow.components.google import GoogleDriveSearchComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestGoogleDriveSearchComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return GoogleDriveSearchComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "token_string": '{"access_token": "fake_access_token", "expires_in": 3600}',
            "query_item": "name",
            "valid_operator": "contains",
            "search_term": "test_file",
            "query_string": "",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "google_drive_search", "file_name": "GoogleDriveSearch"},
        ]

    def test_generate_query_string(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        query_string = component.generate_query_string()
        assert query_string == "name contains 'test_file'"
        assert component.query_string == query_string

    def test_on_inputs_changed(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.search_term = "new_file"
        component.on_inputs_changed()
        assert component.query_string == "name contains 'new_file'"

    def test_generate_file_url(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        file_url = component.generate_file_url("12345", "application/vnd.google-apps.document")
        assert file_url == "https://docs.google.com/document/d/12345/edit"

    async def test_search_doc_ids(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        # Mock the search_files method to return a controlled response
        component.search_files = lambda: {
            "doc_ids": ["1", "2"],
            "doc_urls": ["url1", "url2"],
            "doc_titles_urls": [{"title": "File 1", "url": "url1"}, {"title": "File 2", "url": "url2"}],
            "doc_titles": ["File 1", "File 2"],
        }
        doc_ids = await component.search_doc_ids()
        assert doc_ids == ["1", "2"]

    async def test_search_doc_urls(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        # Mock the search_files method to return a controlled response
        component.search_files = lambda: {
            "doc_ids": ["1", "2"],
            "doc_urls": ["url1", "url2"],
            "doc_titles_urls": [{"title": "File 1", "url": "url1"}, {"title": "File 2", "url": "url2"}],
            "doc_titles": ["File 1", "File 2"],
        }
        doc_urls = await component.search_doc_urls()
        assert doc_urls == ["url1", "url2"]

    async def test_search_doc_titles(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        # Mock the search_files method to return a controlled response
        component.search_files = lambda: {
            "doc_ids": ["1", "2"],
            "doc_urls": ["url1", "url2"],
            "doc_titles_urls": [{"title": "File 1", "url": "url1"}, {"title": "File 2", "url": "url2"}],
            "doc_titles": ["File 1", "File 2"],
        }
        doc_titles = await component.search_doc_titles()
        assert doc_titles == ["File 1", "File 2"]

    async def test_search_data(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        # Mock the search_files method to return a controlled response
        component.search_files = lambda: {
            "doc_ids": ["1", "2"],
            "doc_urls": ["url1", "url2"],
            "doc_titles_urls": [{"title": "File 1", "url": "url1"}, {"title": "File 2", "url": "url2"}],
            "doc_titles": ["File 1", "File 2"],
        }
        data = await component.search_data()
        assert data.data == [{"title": "File 1", "url": "url1"}, {"title": "File 2", "url": "url2"}]

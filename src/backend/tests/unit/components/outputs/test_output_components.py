import pytest
from langflow.components.input_output import TextOutputComponent

from tests.base import ComponentTestBaseWithoutClient


class TestTextOutputComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return TextOutputComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "Hello, world!",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.19", "module": "outputs", "file_name": "TextOutput"},
            {"version": "1.1.0", "module": "outputs", "file_name": "text"},
            {"version": "1.1.1", "module": "outputs", "file_name": "text"},
        ]

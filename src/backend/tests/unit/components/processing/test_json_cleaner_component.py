import pytest
from langflow.components.processing import JSONCleaner

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestJSONCleaner(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return JSONCleaner

    @pytest.fixture
    def default_kwargs(self):
        return {
            "json_str": '{"name": "John", "age": 30, "city": "New York"}',
            "remove_control_chars": False,
            "normalize_unicode": False,
            "validate_json": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "json_cleaner", "file_name": "JSONCleaner"},
        ]

    def test_clean_json_valid(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.clean_json()
        assert result is not None
        assert result.text == '{"name": "John", "age": 30, "city": "New York"}'

    def test_clean_json_with_control_chars(self, component_class):
        default_kwargs = {
            "json_str": '{"name": "John\x00", "age": 30}',
            "remove_control_chars": True,
            "normalize_unicode": False,
            "validate_json": True,
        }
        component = component_class(**default_kwargs)
        result = component.clean_json()
        assert result.text == '{"name": "John", "age": 30}'

    def test_clean_json_invalid(self, component_class):
        default_kwargs = {
            "json_str": '{"name": "John", "age": 30, "city": "New York"',
            "remove_control_chars": False,
            "normalize_unicode": False,
            "validate_json": True,
        }
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Invalid JSON string:"):
            component.clean_json()

    def test_normalize_unicode(self, component_class):
        default_kwargs = {
            "json_str": '{"name": "Jöhn", "age": 30}',
            "remove_control_chars": False,
            "normalize_unicode": True,
            "validate_json": True,
        }
        component = component_class(**default_kwargs)
        result = component.clean_json()
        assert result.text == '{"name": "Jöhn", "age": 30}'

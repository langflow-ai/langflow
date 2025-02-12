from langflow.components.processing.parse_data import ParseDataComponent
import pytest
from langflow.schema import Data, Message
from tests.base import ComponentTestBaseWithoutClient


class TestParseDataComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return ParseDataComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "data": [
                Data(text="Hello", data={"field1": "value1"}),
                Data(text="World", data={"field1": "value2"}),
            ],
            "template": "{text}",
            "sep": "\n",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for different versions."""
        return [
            {"version": "1.1.0", "module": "processing", "file_name": "parse_data"},
            {"version": "1.1.1", "module": "processing", "file_name": "parse_data"},
        ]

    def test_basic_setup(self, component_class, default_kwargs):
        """Test basic component initialization."""
        component = component_class()
        component.set_attributes(default_kwargs)
        assert component.template == default_kwargs["template"]
        assert component.sep == default_kwargs["sep"]
        assert component.data == default_kwargs["data"]

    def test_clean_args_with_list(self, component_class, default_kwargs):
        """Test _clean_args with list input."""
        component = component_class()
        component.set_attributes(default_kwargs)
        data, template, sep = component._clean_args()
        assert isinstance(data, list)
        assert len(data) == 2
        assert template == "{text}"
        assert sep == "\n"

    def test_clean_args_with_single_data(self, component_class):
        """Test _clean_args with single Data input."""
        single_data = Data(text="Single", data={"field1": "value"})
        component = component_class()
        component.set_attributes({"data": single_data, "template": "{text}", "sep": "\n"})
        data, template, sep = component._clean_args()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0].text == "Single"

    def test_parse_data_basic(self, component_class, default_kwargs):
        """Test basic parse_data functionality."""
        component = component_class()
        component.set_attributes(default_kwargs)
        result = component.parse_data()
        assert isinstance(result, Message)
        assert result.text == "Hello\nWorld"
        assert component.status == result.text

    def test_parse_data_custom_template(self, component_class, default_kwargs):
        """Test parse_data with custom template."""
        default_kwargs["template"] = "Data: {text}, Field: {data[field1]}"
        component = component_class()
        component.set_attributes(default_kwargs)
        result = component.parse_data()
        assert isinstance(result, Message)
        assert result.text == "Data: Hello, Field: value1\nData: World, Field: value2"

    def test_parse_data_custom_separator(self, component_class, default_kwargs):
        """Test parse_data with custom separator."""
        default_kwargs["sep"] = " | "
        component = component_class()
        component.set_attributes(default_kwargs)
        result = component.parse_data()
        assert isinstance(result, Message)
        assert result.text == "Hello | World"

    def test_parse_data_empty_list(self, component_class):
        """Test parse_data with empty list."""
        component = component_class()
        component.set_attributes({"data": [], "template": "{text}", "sep": "\n"})
        result = component.parse_data()
        assert isinstance(result, Message)
        assert result.text == ""

    def test_parse_data_as_list_basic(self, component_class, default_kwargs):
        """Test basic parse_data_as_list functionality."""
        component = component_class()
        component.set_attributes(default_kwargs)
        result = component.parse_data_as_list()
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, Data) for item in result)
        assert result[0].text == "Hello"
        assert result[1].text == "World"
        assert component.status == result

    def test_parse_data_as_list_custom_template(self, component_class, default_kwargs):
        """Test parse_data_as_list with custom template."""
        default_kwargs["template"] = "Processed: {text}"
        component = component_class()
        component.set_attributes(default_kwargs)
        result = component.parse_data_as_list()
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].text == "Processed: Hello"
        assert result[1].text == "Processed: World"

    def test_parse_data_nested_fields(self, component_class):
        """Test parsing with nested data fields."""
        nested_data = [
            Data(text="Test1", data={"nested": {"field": "value1"}}),
            Data(text="Test2", data={"nested": {"field": "value2"}}),
        ]
        component = component_class()
        component.set_attributes({
            "data": nested_data,
            "template": "{text} - {data[nested][field]}",
            "sep": "\n"
        })
        result = component.parse_data()
        assert isinstance(result, Message)
        assert result.text == "Test1 - value1\nTest2 - value2"

    def test_missing_required_fields(self, component_class):
        """Test behavior with missing required fields."""
        component = component_class()
        result = component.parse_data()
        assert isinstance(result, Message)
        assert result.text == "" 

    def test_invalid_template_fields(self, component_class, default_kwargs):
        """Test behavior with invalid template fields."""
        default_kwargs["template"] = "{invalid_field}"
        component = component_class()
        component.set_attributes(default_kwargs)
        # Should raise KeyError for invalid template field
        with pytest.raises(KeyError) as exc_info:
            component.parse_data()
        assert "invalid_field" in str(exc_info.value)

    def test_parse_data_preserve_original(self, component_class, default_kwargs):
        """Test that original data is preserved after parsing."""
        component = component_class()
        component.set_attributes(default_kwargs)
        original_data = default_kwargs["data"].copy()
        result = component.parse_data_as_list()
        
        # Check original data wasn't modified
        assert len(original_data) == len(default_kwargs["data"])
        for orig, curr in zip(original_data, default_kwargs["data"]):
            assert orig.text == curr.text
            assert orig.data == curr.data
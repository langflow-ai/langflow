import pytest
from langflow.components.helpers import OutputParserComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestOutputParserComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return OutputParserComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"parser_type": "CSV"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "parsers", "file_name": "OutputParser"},
            {"version": "1.1.0", "module": "parsers", "file_name": "output_parser"},
        ]

    def test_build_parser_csv(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        parser = component.build_parser()
        assert isinstance(parser, CommaSeparatedListOutputParser)

    def test_format_instructions_csv(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        instructions = component.format_instructions()
        assert instructions.text == CommaSeparatedListOutputParser().get_format_instructions()

    def test_build_parser_invalid(self, component_class):
        component = component_class(parser_type="INVALID")
        with pytest.raises(ValueError, match="Unsupported or missing parser"):
            component.build_parser()

    def test_format_instructions_invalid(self, component_class):
        component = component_class(parser_type="INVALID")
        with pytest.raises(ValueError, match="Unsupported or missing parser"):
            component.format_instructions()

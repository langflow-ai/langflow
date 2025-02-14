import pandas as pd
import pytest
from langflow.components.processing.parse_dataframe import ParseDataFrameComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestParseDataFrameComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ParseDataFrameComponent

    @pytest.fixture
    def default_kwargs(self):
        data = {"text": ["Hello", "World"], "number": [1, 2]}
        df = pd.DataFrame(data)
        return {"df": df, "template": "{text} {number}", "sep": "\n"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "parsers", "file_name": "ParseDataFrame"},
        ]

    def test_parse_data(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        result = component.parse_data()

        # Assert
        assert result is not None
        assert result.text == "Hello 1\nWorld 2"
        assert component.status == "Hello 1\nWorld 2"

    def test_empty_dataframe(self, component_class):
        # Arrange
        empty_df = pd.DataFrame(columns=["text", "number"])
        component = component_class(df=empty_df, template="{text} {number}", sep="\n")

        # Act
        result = component.parse_data()

        # Assert
        assert result is not None
        assert result.text == ""
        assert component.status == ""

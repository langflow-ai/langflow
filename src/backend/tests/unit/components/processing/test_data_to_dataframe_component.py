import pytest
from langflow.schema import Data, DataFrame

from lfx.components.processing.data_to_dataframe import DataToDataFrameComponent
from tests.base import ComponentTestBaseWithoutClient


class TestDataToDataFrameComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return DataToDataFrameComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "data_list": [
                Data(text="Row 1", data={"field1": "value1", "field2": 1}),
                Data(text="Row 2", data={"field1": "value2", "field2": 2}),
            ]
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for different versions."""
        # This is a new component, so we return an empty list
        return []

    def test_basic_setup(self, component_class, default_kwargs):
        """Test basic component initialization."""
        component = component_class()
        component.set_attributes(default_kwargs)
        assert component.data_list == default_kwargs["data_list"]

    def test_build_dataframe_basic(self, component_class, default_kwargs):
        """Test basic DataFrame construction."""
        component = component_class()
        component.set_attributes(default_kwargs)
        result_df = component.build_dataframe()

        assert isinstance(result_df, DataFrame)
        assert len(result_df) == 2
        assert list(result_df.columns) == ["field1", "field2", "text"]
        assert result_df["text"].tolist() == ["Row 1", "Row 2"]
        assert result_df["field1"].tolist() == ["value1", "value2"]
        assert result_df["field2"].tolist() == [1, 2]

    def test_single_data_input(self, component_class):
        """Test handling single Data object input."""
        single_data = Data(text="Single Row", data={"field1": "value"})
        component = component_class()
        component.set_attributes({"data_list": single_data})

        result_df = component.build_dataframe()

        assert len(result_df) == 1
        assert result_df["text"].iloc[0] == "Single Row"
        assert result_df["field1"].iloc[0] == "value"

    def test_empty_data_list(self, component_class):
        """Test behavior with empty data list."""
        component = component_class()
        component.set_attributes({"data_list": []})

        result_df = component.build_dataframe()

        assert len(result_df) == 0

    def test_data_without_text(self, component_class):
        """Test handling Data objects without text field."""
        data_without_text = [Data(data={"field1": "value1"}), Data(data={"field1": "value2"})]
        component = component_class()
        component.set_attributes({"data_list": data_without_text})

        result_df = component.build_dataframe()

        assert len(result_df) == 2
        assert "text" not in result_df.columns
        assert result_df["field1"].tolist() == ["value1", "value2"]

    def test_data_without_data_dict(self, component_class):
        """Test handling Data objects without data dictionary."""
        data_without_dict = [Data(text="Text 1"), Data(text="Text 2")]
        component = component_class()
        component.set_attributes({"data_list": data_without_dict})

        result_df = component.build_dataframe()

        assert len(result_df) == 2
        assert list(result_df.columns) == ["text"]
        assert result_df["text"].tolist() == ["Text 1", "Text 2"]

    def test_mixed_data_fields(self, component_class):
        """Test handling Data objects with different fields."""
        mixed_data = [
            Data(text="Row 1", data={"field1": "value1", "field2": 1}),
            Data(text="Row 2", data={"field1": "value2", "field3": "extra"}),
        ]
        component = component_class()
        component.set_attributes({"data_list": mixed_data})

        result_df = component.build_dataframe()

        assert len(result_df) == 2
        assert set(result_df.columns) == {"field1", "field2", "field3", "text"}
        assert result_df["field1"].tolist() == ["value1", "value2"]
        assert result_df["field2"].iloc[1] != result_df["field2"].iloc[1]  # Check for NaN using inequality
        assert result_df["field3"].iloc[0] != result_df["field3"].iloc[0]  # Check for NaN using inequality

    def test_invalid_input_type(self, component_class):
        """Test error handling for invalid input types."""
        invalid_data = [{"not": "a Data object"}]
        component = component_class()
        component.set_attributes({"data_list": invalid_data})

        with pytest.raises(TypeError) as exc_info:
            component.build_dataframe()
        assert "Expected Data objects" in str(exc_info.value)

    def test_status_update(self, component_class, default_kwargs):
        """Test that status is properly updated."""
        component = component_class()
        component.set_attributes(default_kwargs)
        result = component.build_dataframe()

        assert component.status is result  # Status should be set to the DataFrame

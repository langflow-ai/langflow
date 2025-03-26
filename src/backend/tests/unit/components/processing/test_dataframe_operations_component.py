import pandas as pd
import pytest
from langflow.components.processing.dataframe_operations import DataFrameOperationsComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestDataFrameOperationsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return DataFrameOperationsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "df": pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
            "operation": "Add Column",
            "new_column_name": "C",
            "new_column_value": 10,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "dataframe_operations", "file_name": "DataFrameOperations"},
        ]

    def test_perform_add_column(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        result = component.perform_operation()

        # Assert
        expected_df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6], "C": [10, 10, 10]})
        pd.testing.assert_frame_equal(result.to_pandas(), expected_df)

    def test_perform_filter(self, component_class):
        # Arrange
        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        component = component_class(df=df, operation="Filter", column_name="A", filter_value=2)

        # Act
        result = component.perform_operation()

        # Assert
        expected_df = pd.DataFrame({"A": [2], "B": [5]})
        pd.testing.assert_frame_equal(result.to_pandas(), expected_df)

    def test_perform_sort(self, component_class):
        # Arrange
        df = pd.DataFrame({"A": [3, 1, 2], "B": [6, 4, 5]})
        component = component_class(df=df, operation="Sort", column_name="A", ascending=True)

        # Act
        result = component.perform_operation()

        # Assert
        expected_df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        pd.testing.assert_frame_equal(result.to_pandas(), expected_df)

    def test_perform_drop_column(self, component_class):
        # Arrange
        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        component = component_class(df=df, operation="Drop Column", column_name="B")

        # Act
        result = component.perform_operation()

        # Assert
        expected_df = pd.DataFrame({"A": [1, 2, 3]})
        pd.testing.assert_frame_equal(result.to_pandas(), expected_df)

    def test_perform_rename_column(self, component_class):
        # Arrange
        df = pd.DataFrame({"A": [1, 2, 3]})
        component = component_class(df=df, operation="Rename Column", column_name="A", new_column_name="X")

        # Act
        result = component.perform_operation()

        # Assert
        expected_df = pd.DataFrame({"X": [1, 2, 3]})
        pd.testing.assert_frame_equal(result.to_pandas(), expected_df)

    def test_perform_head(self, component_class):
        # Arrange
        df = pd.DataFrame({"A": [1, 2, 3, 4, 5]})
        component = component_class(df=df, operation="Head", num_rows=3)

        # Act
        result = component.perform_operation()

        # Assert
        expected_df = pd.DataFrame({"A": [1, 2, 3]})
        pd.testing.assert_frame_equal(result.to_pandas(), expected_df)

    def test_perform_tail(self, component_class):
        # Arrange
        df = pd.DataFrame({"A": [1, 2, 3, 4, 5]})
        component = component_class(df=df, operation="Tail", num_rows=2)

        # Act
        result = component.perform_operation()

        # Assert
        expected_df = pd.DataFrame({"A": [4, 5]})
        pd.testing.assert_frame_equal(result.to_pandas(), expected_df)

    def test_perform_replace_value(self, component_class):
        # Arrange
        df = pd.DataFrame({"A": [1, 2, 1]})
        component = component_class(
            df=df, operation="Replace Value", column_name="A", replace_value=1, replacement_value=10
        )

        # Act
        result = component.perform_operation()

        # Assert
        expected_df = pd.DataFrame({"A": [10, 2, 10]})
        pd.testing.assert_frame_equal(result.to_pandas(), expected_df)

    def test_perform_select_columns(self, component_class):
        # Arrange
        df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        component = component_class(df=df, operation="Select Columns", columns_to_select=["A"])

        # Act
        result = component.perform_operation()

        # Assert
        expected_df = pd.DataFrame({"A": [1, 2]})
        pd.testing.assert_frame_equal(result.to_pandas(), expected_df)

import pandas as pd
import pytest

from lfx.components.processing.dataframe_operations import DataFrameOperationsComponent
from lfx.schema.dataframe import DataFrame


@pytest.fixture
def sample_dataframe():
    """Create a comprehensive sample DataFrame for testing."""
    data = {
        "name": ["John Doe", "Jane Smith", "Bob Johnson", "Alice Brown", "Charlie Wilson"],
        "email": ["john@gmail.com", "jane@yahoo.com", "bob@gmail.com", "alice@hotmail.com", "charlie@outlook.com"],
        "age": [25, 30, 35, 28, 42],
        "salary": [50000, 60000, 70000, 55000, 80000],
        "department": ["IT", "HR", "Finance", "IT", "Marketing"],
    }
    return DataFrame(pd.DataFrame(data))


@pytest.fixture
def component():
    """Create a DataFrameOperationsComponent instance."""
    return DataFrameOperationsComponent()


class TestBasicOperations:
    """Test basic DataFrame operations with new SortableListInput format."""

    def test_add_column(self, component, sample_dataframe):
        """Test adding a new column to the DataFrame."""
        component.df = sample_dataframe
        component.operation = [{"name": "Add Column", "icon": "plus"}]
        component.new_column_name = "bonus"
        component.new_column_value = 5000

        result = component.perform_operation()

        assert "bonus" in result.columns
        assert len(result.columns) == 6  # Original 5 + 1 new
        assert all(result["bonus"] == 5000)  # All values should be 5000

    def test_drop_column(self, component, sample_dataframe):
        """Test dropping a column from the DataFrame."""
        component.df = sample_dataframe
        component.operation = [{"name": "Drop Column", "icon": "minus"}]
        component.column_name = "salary"

        result = component.perform_operation()

        assert "salary" not in result.columns
        assert len(result.columns) == 4  # Original 5 - 1 dropped

    def test_sort_ascending(self, component, sample_dataframe):
        """Test sorting DataFrame in ascending order."""
        component.df = sample_dataframe
        component.operation = [{"name": "Sort", "icon": "arrow-up-down"}]
        component.column_name = "age"
        component.ascending = True

        result = component.perform_operation()

        ages = result["age"].tolist()
        assert ages == sorted(ages)  # Should be sorted ascending
        assert ages[0] == 25  # Youngest first

    def test_sort_descending(self, component, sample_dataframe):
        """Test sorting DataFrame in descending order."""
        component.df = sample_dataframe
        component.operation = [{"name": "Sort", "icon": "arrow-up-down"}]
        component.column_name = "salary"
        component.ascending = False

        result = component.perform_operation()

        salaries = result["salary"].tolist()
        assert salaries == sorted(salaries, reverse=True)  # Should be sorted descending
        assert salaries[0] == 80000  # Highest first

    def test_head_operation(self, component, sample_dataframe):
        """Test getting first N rows."""
        component.df = sample_dataframe
        component.operation = [{"name": "Head", "icon": "arrow-up"}]
        component.num_rows = 2

        result = component.perform_operation()

        assert len(result) == 2
        assert result.iloc[0]["name"] == "John Doe"  # First row

    def test_tail_operation(self, component, sample_dataframe):
        """Test getting last N rows."""
        component.df = sample_dataframe
        component.operation = [{"name": "Tail", "icon": "arrow-down"}]
        component.num_rows = 2

        result = component.perform_operation()

        assert len(result) == 2
        assert result.iloc[-1]["name"] == "Charlie Wilson"  # Last row

    def test_rename_column(self, component, sample_dataframe):
        """Test renaming a column."""
        component.df = sample_dataframe
        component.operation = [{"name": "Rename Column", "icon": "pencil"}]
        component.column_name = "name"
        component.new_column_name = "full_name"

        result = component.perform_operation()

        assert "full_name" in result.columns
        assert "name" not in result.columns
        assert result.iloc[0]["full_name"] == "John Doe"


class TestFilterOperations:
    """Test all filter operations with different operators."""

    def test_filter_equals(self, component, sample_dataframe):
        """Test exact match filtering."""
        component.df = sample_dataframe
        component.operation = [{"name": "Filter", "icon": "filter"}]
        component.column_name = "department"
        component.filter_operator = "equals"
        component.filter_value = "IT"

        result = component.perform_operation()

        assert len(result) == 2  # John and Alice work in IT
        assert all(result["department"] == "IT")

    def test_filter_not_equals(self, component, sample_dataframe):
        """Test exclusion filtering."""
        component.df = sample_dataframe
        component.operation = [{"name": "Filter", "icon": "filter"}]
        component.column_name = "department"
        component.filter_operator = "not equals"
        component.filter_value = "IT"

        result = component.perform_operation()

        assert len(result) == 3  # Jane, Bob, Charlie not in IT
        assert all(result["department"] != "IT")

    def test_filter_contains(self, component, sample_dataframe):
        """Test partial string matching - THE MAIN FEATURE WE ADDED!"""
        component.df = sample_dataframe
        component.operation = [{"name": "Filter", "icon": "filter"}]
        component.column_name = "email"
        component.filter_operator = "contains"
        component.filter_value = "gmail"

        result = component.perform_operation()

        assert len(result) == 2  # John and Bob have gmail
        assert all("gmail" in email for email in result["email"])

    def test_filter_starts_with(self, component, sample_dataframe):
        """Test prefix matching."""
        component.df = sample_dataframe
        component.operation = [{"name": "Filter", "icon": "filter"}]
        component.column_name = "name"
        component.filter_operator = "starts with"
        component.filter_value = "J"

        result = component.perform_operation()

        assert len(result) == 2  # John and Jane start with J
        assert all(name.startswith("J") for name in result["name"])

    def test_filter_ends_with(self, component, sample_dataframe):
        """Test suffix matching."""
        component.df = sample_dataframe
        component.operation = [{"name": "Filter", "icon": "filter"}]
        component.column_name = "email"
        component.filter_operator = "ends with"
        component.filter_value = ".com"

        result = component.perform_operation()

        assert len(result) == 5  # All emails end with .com
        assert all(email.endswith(".com") for email in result["email"])

    def test_filter_greater_than(self, component, sample_dataframe):
        """Test numeric greater than comparison."""
        component.df = sample_dataframe
        component.operation = [{"name": "Filter", "icon": "filter"}]
        component.column_name = "age"
        component.filter_operator = "greater than"
        component.filter_value = "30"

        result = component.perform_operation()

        assert len(result) == 2  # Bob(35) and Charlie(42)
        assert all(age > 30 for age in result["age"])

    def test_filter_less_than(self, component, sample_dataframe):
        """Test numeric less than comparison."""
        component.df = sample_dataframe
        component.operation = [{"name": "Filter", "icon": "filter"}]
        component.column_name = "salary"
        component.filter_operator = "less than"
        component.filter_value = "60000"

        result = component.perform_operation()

        assert len(result) == 2  # John(50k) and Alice(55k)
        assert all(salary < 60000 for salary in result["salary"])


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_selection(self, component, sample_dataframe):
        """Test when no operation is selected (deselection)."""
        component.df = sample_dataframe
        component.operation = []  # Empty selection

        result = component.perform_operation()

        # Should return original DataFrame unchanged
        assert len(result) == len(sample_dataframe)
        assert list(result.columns) == list(sample_dataframe.columns)

    def test_invalid_operation_format(self, component, sample_dataframe):
        """Test with invalid operation format."""
        component.df = sample_dataframe
        component.operation = "Invalid String"  # Not list format

        result = component.perform_operation()

        # Should return original DataFrame
        assert len(result) == len(sample_dataframe)

    def test_empty_dataframe(self, component):
        """Test operations on empty DataFrame."""
        component.df = DataFrame(pd.DataFrame())
        component.operation = [{"name": "Head", "icon": "arrow-up"}]
        component.num_rows = 3

        result = component.perform_operation()

        assert result.empty

    def test_non_existent_column(self, component, sample_dataframe):
        """Test operation on non-existent column."""
        component.df = sample_dataframe
        component.operation = [{"name": "Drop Column", "icon": "minus"}]
        component.column_name = "non_existent_column"

        with pytest.raises(KeyError):
            component.perform_operation()

    def test_filter_no_matches(self, component, sample_dataframe):
        """Test filter that returns no matches."""
        component.df = sample_dataframe
        component.operation = [{"name": "Filter", "icon": "filter"}]
        component.column_name = "department"
        component.filter_operator = "equals"
        component.filter_value = "NonExistentDepartment"

        result = component.perform_operation()

        assert len(result) == 0  # No matches
        assert list(result.columns) == list(sample_dataframe.columns)  # Columns preserved


class TestDynamicUI:
    """Test dynamic UI behavior with update_build_config."""

    def test_filter_fields_show(self, component):
        """Test that filter fields show when Filter is selected."""
        build_config = {
            "column_name": {"show": False},
            "filter_value": {"show": False},
            "filter_operator": {"show": False},
            "ascending": {"show": False},
            "new_column_name": {"show": False},
            "new_column_value": {"show": False},
            "columns_to_select": {"show": False},
            "num_rows": {"show": False},
            "replace_value": {"show": False},
            "replacement_value": {"show": False},
        }

        # Select Filter operation
        updated_config = component.update_build_config(
            build_config, [{"name": "Filter", "icon": "filter"}], "operation"
        )

        assert updated_config["column_name"]["show"] is True
        assert updated_config["filter_value"]["show"] is True
        assert updated_config["filter_operator"]["show"] is True
        assert updated_config["ascending"]["show"] is False  # Not for filter

    def test_sort_fields_show(self, component):
        """Test that sort fields show when Sort is selected."""
        build_config = {
            "column_name": {"show": False},
            "filter_value": {"show": False},
            "filter_operator": {"show": False},
            "ascending": {"show": False},
            "new_column_name": {"show": False},
            "new_column_value": {"show": False},
            "columns_to_select": {"show": False},
            "num_rows": {"show": False},
            "replace_value": {"show": False},
            "replacement_value": {"show": False},
        }

        # Select Sort operation
        updated_config = component.update_build_config(
            build_config, [{"name": "Sort", "icon": "arrow-up-down"}], "operation"
        )

        assert updated_config["column_name"]["show"] is True
        assert updated_config["ascending"]["show"] is True
        assert updated_config["filter_value"]["show"] is False  # Not for sort
        assert updated_config["filter_operator"]["show"] is False  # Not for sort

    def test_empty_selection_hides_fields(self, component):
        """Test that all fields hide when operation is deselected."""
        build_config = {
            "column_name": {"show": True},
            "filter_value": {"show": True},
            "filter_operator": {"show": True},
            "ascending": {"show": True},
            "new_column_name": {"show": True},
            "new_column_value": {"show": True},
            "columns_to_select": {"show": True},
            "num_rows": {"show": True},
            "replace_value": {"show": True},
            "replacement_value": {"show": True},
        }

        # Deselect operation (empty list)
        updated_config = component.update_build_config(
            build_config,
            [],  # Empty selection
            "operation",
        )

        # All fields should be hidden
        assert updated_config["column_name"]["show"] is False
        assert updated_config["filter_value"]["show"] is False
        assert updated_config["filter_operator"]["show"] is False
        assert updated_config["ascending"]["show"] is False
        assert updated_config["new_column_name"]["show"] is False
        assert updated_config["new_column_value"]["show"] is False
        assert updated_config["columns_to_select"]["show"] is False
        assert updated_config["num_rows"]["show"] is False
        assert updated_config["replace_value"]["show"] is False
        assert updated_config["replacement_value"]["show"] is False


class TestDataTypes:
    """Test different data types and conversions."""

    def test_numeric_string_conversion(self, component):
        """Test that string numbers are properly converted for comparison."""
        data = pd.DataFrame({"values": [10, 20, 30, 40, 50], "names": ["a", "b", "c", "d", "e"]})

        component.df = DataFrame(data)
        component.operation = [{"name": "Filter", "icon": "filter"}]
        component.column_name = "values"
        component.filter_operator = "greater than"
        component.filter_value = "25"  # String input

        result = component.perform_operation()

        assert len(result) == 3  # 30, 40, 50 are > 25
        assert all(val > 25 for val in result["values"])

    def test_mixed_data_types(self, component):
        """Test filtering on mixed data types."""
        data = pd.DataFrame({"mixed": ["text", 123, "more_text", 456], "id": [1, 2, 3, 4]})

        component.df = DataFrame(data)
        component.operation = [{"name": "Filter", "icon": "filter"}]
        component.column_name = "mixed"
        component.filter_operator = "contains"
        component.filter_value = "text"

        result = component.perform_operation()

        assert len(result) == 2  # "text" and "more_text"


# Integration test to verify all operators work together
def test_all_filter_operators_comprehensive():
    """Comprehensive test of all filter operators on the same dataset."""
    data = pd.DataFrame(
        {
            "name": ["John", "Jane", "Bob", "Alice"],
            "email": ["john@gmail.com", "jane@yahoo.com", "bob@gmail.com", "alice@test.org"],
            "age": [25, 30, 35, 28],
            "score": [85.5, 92.0, 78.5, 88.0],
        }
    )

    component = DataFrameOperationsComponent()
    component.df = DataFrame(data)
    component.operation = [{"name": "Filter", "icon": "filter"}]

    # Test all operators
    test_cases = [
        ("email", "contains", "gmail", 2),  # John, Bob
        ("name", "starts with", "J", 2),  # John, Jane
        ("email", "ends with", ".com", 3),  # All except Alice
        ("age", "greater than", "28", 2),  # Jane, Bob
        ("score", "less than", "90", 3),  # John, Bob, Alice
        ("name", "equals", "John", 1),  # Only John
        ("email", "not equals", "jane@yahoo.com", 3),  # All except Jane
    ]

    for column, operator, value, expected_count in test_cases:
        component.column_name = column
        component.filter_operator = operator
        component.filter_value = value

        result = component.perform_operation()

        assert len(result) == expected_count, f"Failed for {operator} on {column} with value {value}"


if __name__ == "__main__":
    pytest.main([__file__])

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
        """Test with invalid operation format raises error."""
        component.df = sample_dataframe
        component.operation = "Invalid String"  # Not list format

        with pytest.raises(ValueError, match="Unsupported operation"):
            component.perform_operation()

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
            "merge_on_column": {"show": False},
            "merge_how": {"show": False},
            "left_dataframe": {"show": False},
            "right_dataframe": {"show": False},
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
            "merge_on_column": {"show": False},
            "merge_how": {"show": False},
            "left_dataframe": {"show": False},
            "right_dataframe": {"show": False},
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
            "merge_on_column": {"show": True},
            "merge_how": {"show": True},
            "left_dataframe": {"show": True},
            "right_dataframe": {"show": True},
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
        assert updated_config["merge_on_column"]["show"] is False
        assert updated_config["merge_how"]["show"] is False
        assert updated_config["left_dataframe"]["show"] is False
        assert updated_config["right_dataframe"]["show"] is False


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


class TestConcatenateOperation:
    """Test concatenate operation for combining multiple DataFrames."""

    def test_concatenate_two_dataframes(self, component):
        """Test concatenating two DataFrames vertically."""
        df1 = DataFrame(pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]}))
        df2 = DataFrame(pd.DataFrame({"id": [3, 4], "name": ["Charlie", "Diana"]}))

        component.df = [df1, df2]
        component.operation = [{"name": "Concatenate", "icon": "combine"}]

        result = component.perform_operation()

        assert len(result) == 4
        assert list(result["id"]) == [1, 2, 3, 4]
        assert list(result["name"]) == ["Alice", "Bob", "Charlie", "Diana"]

    def test_concatenate_single_dataframe(self, component):
        """Test concatenate with only one DataFrame returns it unchanged."""
        df1 = DataFrame(pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]}))

        component.df = [df1]
        component.operation = [{"name": "Concatenate", "icon": "combine"}]

        result = component.perform_operation()

        assert len(result) == 2
        assert list(result["id"]) == [1, 2]

    def test_concatenate_different_row_counts(self, component):
        """Test concatenating DataFrames with different row counts."""
        df1 = DataFrame(pd.DataFrame({"id": [1, 2, 3], "value": ["a", "b", "c"]}))
        df2 = DataFrame(pd.DataFrame({"id": [4, 5], "value": ["d", "e"]}))

        component.df = [df1, df2]
        component.operation = [{"name": "Concatenate", "icon": "combine"}]

        result = component.perform_operation()

        assert len(result) == 5


class TestMergeOperation:
    """Test merge operation for joining DataFrames."""

    def test_merge_inner_join(self, component):
        """Test inner merge on common column."""
        df1 = DataFrame(pd.DataFrame({"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"]}))
        df2 = DataFrame(pd.DataFrame({"id": [2, 3, 4], "city": ["NYC", "LA", "Chicago"]}))

        component.left_dataframe = df1
        component.right_dataframe = df2
        component.operation = [{"name": "Merge", "icon": "merge"}]
        component.merge_on_column = "id"
        component.merge_how = "inner"

        result = component.perform_operation()

        assert len(result) == 2  # Only ids 2 and 3 exist in both
        assert "name" in result.columns
        assert "city" in result.columns

    def test_merge_outer_join(self, component):
        """Test outer merge includes all records."""
        df1 = DataFrame(pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]}))
        df2 = DataFrame(pd.DataFrame({"id": [2, 3], "city": ["NYC", "LA"]}))

        component.left_dataframe = df1
        component.right_dataframe = df2
        component.operation = [{"name": "Merge", "icon": "merge"}]
        component.merge_on_column = "id"
        component.merge_how = "outer"

        result = component.perform_operation()

        assert len(result) == 3  # ids 1, 2, 3

    def test_merge_left_join(self, component):
        """Test left merge keeps all records from left DataFrame."""
        df1 = DataFrame(pd.DataFrame({"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"]}))
        df2 = DataFrame(pd.DataFrame({"id": [2, 4], "city": ["NYC", "Chicago"]}))

        component.left_dataframe = df1
        component.right_dataframe = df2
        component.operation = [{"name": "Merge", "icon": "merge"}]
        component.merge_on_column = "id"
        component.merge_how = "left"

        result = component.perform_operation()

        assert len(result) == 3  # All from left (df1)

    def test_merge_right_join(self, component):
        """Test right merge keeps all records from right DataFrame."""
        df1 = DataFrame(pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]}))
        df2 = DataFrame(pd.DataFrame({"id": [2, 3, 4], "city": ["NYC", "LA", "Chicago"]}))

        component.left_dataframe = df1
        component.right_dataframe = df2
        component.operation = [{"name": "Merge", "icon": "merge"}]
        component.merge_on_column = "id"
        component.merge_how = "right"

        result = component.perform_operation()

        assert len(result) == 3  # All from right (df2)

    def test_should_preserve_left_rows_when_left_merge_with_explicit_inputs(self, component):
        """Test that left merge deterministically preserves all rows from the explicit left DataFrame.

        This is the core bug fix test: with overlapping but distinct customer_ids,
        a left merge must always keep all rows from left_dataframe regardless of
        connection order.
        """
        # Arrange — exact scenario from bug report
        df_a = DataFrame(
            pd.DataFrame(
                {
                    "customer_id": ["CUST-001", "CUST-002", "CUST-003", "CUST-004"],
                    "name": ["Alice", "Bob", "Carol", "David"],
                }
            )
        )
        df_b = DataFrame(
            pd.DataFrame(
                {
                    "customer_id": ["CUST-001", "CUST-002", "CUST-005", "CUST-006"],
                    "product": ["Notebook", "Mouse", "Keyboard", "Monitor"],
                }
            )
        )

        # Act — df_a is explicitly set as left, df_b as right
        component.left_dataframe = df_a
        component.right_dataframe = df_b
        component.operation = [{"name": "Merge", "icon": "merge"}]
        component.merge_on_column = "customer_id"
        component.merge_how = "left"

        result = component.perform_operation()

        # Assert — all 4 rows from left (df_a) must be preserved
        result_ids = sorted(result["customer_id"].tolist())
        assert result_ids == ["CUST-001", "CUST-002", "CUST-003", "CUST-004"]
        assert len(result) == 4
        # CUST-003 and CUST-004 should have NaN product (not in df_b)
        assert pd.isna(result.loc[result["customer_id"] == "CUST-003", "product"].iloc[0])
        assert pd.isna(result.loc[result["customer_id"] == "CUST-004", "product"].iloc[0])

    def test_should_preserve_right_rows_when_right_merge_with_explicit_inputs(self, component):
        """Test that right merge deterministically preserves all rows from the explicit right DataFrame."""
        # Arrange — same data, but now we want df_b's rows preserved
        df_a = DataFrame(
            pd.DataFrame(
                {
                    "customer_id": ["CUST-001", "CUST-002", "CUST-003", "CUST-004"],
                    "name": ["Alice", "Bob", "Carol", "David"],
                }
            )
        )
        df_b = DataFrame(
            pd.DataFrame(
                {
                    "customer_id": ["CUST-001", "CUST-002", "CUST-005", "CUST-006"],
                    "product": ["Notebook", "Mouse", "Keyboard", "Monitor"],
                }
            )
        )

        # Act — df_a is left, df_b is right, merge type is "right"
        component.left_dataframe = df_a
        component.right_dataframe = df_b
        component.operation = [{"name": "Merge", "icon": "merge"}]
        component.merge_on_column = "customer_id"
        component.merge_how = "right"

        result = component.perform_operation()

        # Assert — all 4 rows from right (df_b) must be preserved
        result_ids = sorted(result["customer_id"].tolist())
        assert result_ids == ["CUST-001", "CUST-002", "CUST-005", "CUST-006"]
        assert len(result) == 4
        # CUST-005 and CUST-006 should have NaN name (not in df_a)
        assert pd.isna(result.loc[result["customer_id"] == "CUST-005", "name"].iloc[0])
        assert pd.isna(result.loc[result["customer_id"] == "CUST-006", "name"].iloc[0])

    def test_should_swap_results_when_left_right_inputs_are_swapped(self, component):
        """Test that swapping left/right inputs produces different, deterministic results."""
        df_a = DataFrame(
            pd.DataFrame(
                {
                    "customer_id": ["CUST-001", "CUST-002", "CUST-003"],
                    "name": ["Alice", "Bob", "Carol"],
                }
            )
        )
        df_b = DataFrame(
            pd.DataFrame(
                {
                    "customer_id": ["CUST-002", "CUST-004"],
                    "city": ["NYC", "Chicago"],
                }
            )
        )

        # Left merge with df_a as left
        component.left_dataframe = df_a
        component.right_dataframe = df_b
        component.operation = [{"name": "Merge", "icon": "merge"}]
        component.merge_on_column = "customer_id"
        component.merge_how = "left"
        result_a_left = component.perform_operation()

        # Left merge with df_b as left (swapped)
        component.left_dataframe = df_b
        component.right_dataframe = df_a
        result_b_left = component.perform_operation()

        # Results must be different — df_a has 3 rows, df_b has 2
        assert len(result_a_left) == 3  # All from df_a
        assert len(result_b_left) == 2  # All from df_b

    def test_merge_single_dataframe_returns_original(self, component):
        """Test merge with single left DataFrame and no right returns it unchanged."""
        df1 = DataFrame(pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]}))

        component.left_dataframe = df1
        component.right_dataframe = None
        component.operation = [{"name": "Merge", "icon": "merge"}]
        component.merge_on_column = "id"
        component.merge_how = "inner"

        result = component.perform_operation()

        assert len(result) == 2

    def test_merge_invalid_column_raises_error(self, component):
        """Test merge with non-existent column raises ValueError."""
        df1 = DataFrame(pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]}))
        df2 = DataFrame(pd.DataFrame({"id": [2, 3], "city": ["NYC", "LA"]}))

        component.left_dataframe = df1
        component.right_dataframe = df2
        component.operation = [{"name": "Merge", "icon": "merge"}]
        component.merge_on_column = "non_existent"
        component.merge_how = "inner"

        with pytest.raises(ValueError, match="not found in left DataFrame"):
            component.perform_operation()

    def test_merge_same_columns_coalesces_values(self, component):
        """Test merge with same columns uses coalesce (left value or right value)."""
        df1 = DataFrame(pd.DataFrame({"id": [1, 2], "value": ["a", "b"]}))
        df2 = DataFrame(pd.DataFrame({"id": [2, 3], "value": ["x", "y"]}))

        component.left_dataframe = df1
        component.right_dataframe = df2
        component.operation = [{"name": "Merge", "icon": "merge"}]
        component.merge_on_column = "id"
        component.merge_how = "outer"

        result = component.perform_operation()

        assert len(result) == 3
        # Check no duplicate columns with _right suffix
        assert "value_right" not in result.columns
        # Verify coalesced values
        assert result.loc[result["id"] == 1, "value"].iloc[0] == "a"  # from left
        assert result.loc[result["id"] == 2, "value"].iloc[0] == "b"  # from left (coalesced)
        assert result.loc[result["id"] == 3, "value"].iloc[0] == "y"  # from right


class TestListInputHandling:
    """Test that component handles list inputs correctly."""

    def test_operations_use_first_dataframe_from_list(self, component):
        """Test that non-merge operations use only the first DataFrame."""
        df1 = DataFrame(pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]}))
        df2 = DataFrame(pd.DataFrame({"id": [3, 4], "name": ["Charlie", "Diana"]}))

        component.df = [df1, df2]
        component.operation = [{"name": "Head", "icon": "arrow-up"}]
        component.num_rows = 1

        result = component.perform_operation()

        assert len(result) == 1
        assert result.iloc[0]["name"] == "Alice"  # From first DataFrame


class TestMergeDynamicUI:
    """Test dynamic UI for Merge and Concatenate operations."""

    def test_merge_fields_show(self, component):
        """Test that merge fields show when Merge is selected."""
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
            "merge_on_column": {"show": False},
            "merge_how": {"show": False},
            "left_dataframe": {"show": False},
            "right_dataframe": {"show": False},
        }

        updated_config = component.update_build_config(build_config, [{"name": "Merge", "icon": "merge"}], "operation")

        assert updated_config["merge_on_column"]["show"] is True
        assert updated_config["merge_how"]["show"] is True
        assert updated_config["left_dataframe"]["show"] is True
        assert updated_config["right_dataframe"]["show"] is True
        assert updated_config["column_name"]["show"] is False

    def test_concatenate_hides_all_extra_fields(self, component):
        """Test that Concatenate operation hides all extra fields."""
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
            "merge_on_column": {"show": True},
            "merge_how": {"show": True},
            "left_dataframe": {"show": True},
            "right_dataframe": {"show": True},
        }

        updated_config = component.update_build_config(
            build_config, [{"name": "Concatenate", "icon": "combine"}], "operation"
        )

        # Concatenate doesn't need any extra fields
        assert updated_config["column_name"]["show"] is False
        assert updated_config["merge_on_column"]["show"] is False
        assert updated_config["merge_how"]["show"] is False
        assert updated_config["left_dataframe"]["show"] is False
        assert updated_config["right_dataframe"]["show"] is False


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

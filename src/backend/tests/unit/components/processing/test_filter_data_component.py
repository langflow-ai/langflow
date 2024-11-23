import pytest
from langflow.components.processing import FilterDataComponent
from langflow.schema import Data

from tests.base import ComponentTestBaseWithoutClient


class TestFilterDataComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return FilterDataComponent

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.17", "module": "helpers", "file_name": "FilterData"},
            {"version": "1.0.18", "module": "helpers", "file_name": "FilterData"},
            {"version": "1.0.19", "module": "helpers", "file_name": "FilterData"},
        ]

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": [
                Data(data={"name": "John", "age": 30, "city": "New York"}),
                Data(data={"name": "Jane", "age": 25, "city": "Boston"}),
            ],
            "index": None,
            "select_columns": [],
            "jq_query": "",
        }

    def test_basic_filtering(self, component_class, default_kwargs):
        """Test basic data filtering without any transformations."""
        component = component_class(**default_kwargs)
        result = component.process_data()

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, Data) for item in result)
        assert result[0].data == {"name": "John", "age": 30, "city": "New York"}
        assert result[1].data == {"name": "Jane", "age": 25, "city": "Boston"}

    def test_index_filtering(self, component_class, default_kwargs):
        """Test filtering by index."""
        default_kwargs["jq_query"] = ".[0]"
        component = component_class(**default_kwargs)
        result = component.process_data()

        assert isinstance(result, Data)
        assert result.data == {"name": "John", "age": 30, "city": "New York"}

    def test_column_filtering(self, component_class, default_kwargs):
        """Test filtering specific columns."""
        default_kwargs["select_columns"] = ["name", "age"]
        component = component_class(**default_kwargs)
        result = component.process_data()

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].data == {"name": "John", "age": 30}
        assert result[1].data == {"name": "Jane", "age": 25}

    def test_jq_query_filtering(self, component_class, default_kwargs):
        """Test filtering with JQ query."""
        default_kwargs["jq_query"] = ".[] | {name}"
        component = component_class(**default_kwargs)
        result = component.process_data()

        assert isinstance(result, Data)
        assert "results" in result.data
        assert len(result.data["results"]) == 2
        assert result.data["results"][0] == {"name": "John"}
        assert result.data["results"][1] == {"name": "Jane"}

    def test_combined_filtering(self, component_class, default_kwargs):
        """Test combining multiple filtering methods."""
        default_kwargs.update({"select_columns": ["name", "city"], "jq_query": ".[1]"})
        component = component_class(**default_kwargs)
        result = component.process_data()

        assert isinstance(result, Data)
        assert result.data == {"name": "Jane", "city": "Boston"}

    def test_empty_input(self, component_class):
        """Test handling empty input."""
        component = component_class(input_value=[], index=None, select_columns=[], jq_query="")
        result = component.process_data()

        assert isinstance(result, list)
        assert len(result) == 0

    def test_invalid_jq_query(self, component_class, default_kwargs):
        """Test handling invalid JQ query."""
        default_kwargs["jq_query"] = "invalid_query"
        component = component_class(**default_kwargs)

        with pytest.raises(ValueError, match="Error processing data"):
            component.process_data()

    def test_single_data_input(self, component_class):
        """Test handling single Data object input."""
        single_input = Data(data={"name": "John", "age": 30, "city": "New York"})
        component = component_class(input_value=single_input, index=None, select_columns=[], jq_query="")
        result = component.process_data()

        assert isinstance(result, Data)
        assert result.data == {"name": "John", "age": 30, "city": "New York"}

    def test_non_existent_columns(self, component_class, default_kwargs):
        """Test filtering with non-existent columns."""
        default_kwargs["select_columns"] = ["name", "non_existent"]
        component = component_class(**default_kwargs)
        result = component.process_data()

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].data == {"name": "John"}
        assert result[1].data == {"name": "Jane"}

    def test_primitive_data_handling(self, component_class):
        """Test handling primitive data types."""
        component = component_class(
            input_value=[Data(data={"value": 1}), Data(data={"value": "text"})],
            index=None,
            select_columns=[],
            jq_query="",
        )
        result = component.process_data()

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].data == {"value": 1}
        assert result[1].data == {"value": "text"}

    def test_complex_nested_data(self, component_class):
        """Test filtering with complex nested data structures."""
        complex_data = [
            Data(
                data={
                    "user": {
                        "name": "John",
                        "contact": {
                            "email": "john@example.com",
                            "phone": {"home": "123-456-7890", "work": "098-765-4321"},
                        },
                        "preferences": ["reading", "hiking"],
                    },
                    "orders": [{"id": 1, "items": ["book", "laptop"]}, {"id": 2, "items": ["phone"]}],
                }
            ),
            Data(
                data={
                    "user": {
                        "name": "Jane",
                        "contact": {"email": "jane@example.com", "phone": {"mobile": "555-555-5555"}},
                        "preferences": ["swimming"],
                    },
                    "orders": [{"id": 3, "items": ["tablet"]}],
                }
            ),
        ]

        # Test deep nested field selection
        component = component_class(
            input_value=complex_data, jq_query=".[] | {name: .user.name, email: .user.contact.email}"
        )
        result = component.process_data()
        assert isinstance(result, Data)
        assert "results" in result.data
        assert len(result.data["results"]) == 2
        assert result.data["results"][0] == {"name": "John", "email": "john@example.com"}
        assert result.data["results"][1] == {"name": "Jane", "email": "jane@example.com"}

        # Add test for single item selection
        component = component_class(input_value=complex_data, jq_query=".[0].user.contact.phone")
        result = component.process_data()
        assert isinstance(result, Data)
        assert result.data == {"home": "123-456-7890", "work": "098-765-4321"}

    def test_mixed_data_types(self, component_class):
        """Test filtering with mixed data types including arrays, nulls, and numbers."""
        mixed_data = [
            Data(
                data={
                    "id": 1,
                    "metrics": {"values": [1.5, 2.3, None, 4.7], "average": 2.83, "valid": True},
                    "tags": ["important", None, "urgent"],
                    "metadata": None,
                    "status": {
                        "active": True,
                        "lastUpdated": "2024-01-01",
                        "counts": {"success": 10, "failure": 0, "skipped": None},
                    },
                }
            )
        ]

        # Test handling null values
        component = component_class(input_value=mixed_data, jq_query=".[0].metrics.values | map(select(. != null))")
        result = component.process_data()
        assert isinstance(result, Data)
        assert "results" in result.data
        assert result.data["results"] == [1.5, 2.3, 4.7]

    def test_array_operations(self, component_class):
        """Test complex array operations and transformations."""
        array_data = [
            Data(
                data={
                    "students": [
                        {"name": "Alice", "grades": [85, 90, 92], "active": True},
                        {"name": "Bob", "grades": [75, 88, 95], "active": True},
                        {"name": "Charlie", "grades": [70, 65, 88], "active": False},
                    ],
                    "class_average": 83.1,
                }
            )
        ]

        # Test array filtering and transformation
        component = component_class(
            input_value=array_data,
            jq_query="""
            .[0].students | map(
                select(.active == true) |
                {
                    name,
                    average: (.grades | add / length),
                    passed: (.grades | all(. >= 75))
                }
            )
            """,
        )
        result = component.process_data()
        assert isinstance(result, Data)
        assert "results" in result.data
        assert len(result.data["results"]) == 2
        assert result.data["results"][0]["name"] == "Alice"
        assert result.data["results"][0]["passed"] is True
        assert isinstance(result.data["results"][0]["average"], int | float)
        assert result.data["results"][1]["name"] == "Bob"

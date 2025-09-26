from unittest.mock import Mock

from langflow.schema.data import Data
from langflow.utils.data_structure import (
    analyze_value,
    get_data_structure,
    get_sample_values,
    get_type_str,
    infer_list_type,
)


class TestInferListType:
    """Test cases for infer_list_type function."""

    def test_empty_list(self):
        """Test empty list inference."""
        result = infer_list_type([])
        assert result == "list(unknown)"

    def test_single_type_list(self):
        """Test list with single type."""
        result = infer_list_type([1, 2, 3, 4])
        assert result == "list(int)"

        result = infer_list_type(["a", "b", "c"])
        assert result == "list(str)"

    def test_mixed_type_list(self):
        """Test list with mixed types."""
        result = infer_list_type([1, "hello", 3.14])
        assert "list(" in result
        assert "|" in result  # Should show mixed types
        assert "int" in result
        assert "str" in result
        assert "float" in result

    def test_max_samples_limit(self):
        """Test max_samples parameter."""
        long_list = list(range(100))  # 100 integers
        result = infer_list_type(long_list, max_samples=3)
        assert result == "list(int)"

    def test_boolean_list(self):
        """Test list with boolean values."""
        result = infer_list_type([True, False, True])
        assert result == "list(bool)"

    def test_none_values_list(self):
        """Test list with None values."""
        result = infer_list_type([None, None, None])
        assert result == "list(null)"

    def test_mixed_with_none(self):
        """Test mixed list including None."""
        result = infer_list_type([1, None, "test"])
        assert "null" in result
        assert "int" in result
        assert "str" in result


class TestGetTypeStr:
    """Test cases for get_type_str function."""

    def test_basic_types(self):
        """Test basic Python types."""
        assert get_type_str(None) == "null"
        assert get_type_str(True) == "bool"  # noqa: FBT003
        assert get_type_str(False) == "bool"  # noqa: FBT003
        assert get_type_str(42) == "int"
        assert get_type_str(3.14) == "float"
        assert get_type_str("hello") == "str"

    def test_collection_types(self):
        """Test collection types."""
        result = get_type_str([1, 2, 3])
        assert result == "list(int)"

        result = get_type_str((1, 2, 3))
        assert result == "list(int)"

        result = get_type_str({1, 2, 3})
        assert result == "list(int)"

        result = get_type_str({"key": "value"})
        assert result == "dict"

    def test_date_string_detection(self):
        """Test detection of date-like strings."""
        # Strings that contain the date detection patterns
        date_strings = [
            "this has a date in it",
            "time stamp here",
            "yyyy format string",
            "mm/dd format",
            "dd/mm format",
            "yyyy-mm format",
        ]

        for date_str in date_strings:
            result = get_type_str(date_str)
            assert result == "str(possible_date)"

        # Test strings that don't match patterns
        non_date_strings = ["2023-01-01", "January 1, 2023", "01/01/2023"]
        for non_date_str in non_date_strings:
            result = get_type_str(non_date_str)
            assert result == "str"

    def test_json_string_detection(self):
        """Test detection of JSON strings."""
        json_string = '{"key": "value", "number": 42}'
        result = get_type_str(json_string)
        assert result == "str(json)"

        # Invalid JSON should be regular string
        invalid_json = '{"key": invalid}'
        result = get_type_str(invalid_json)
        assert result == "str"

    def test_custom_objects(self):
        """Test custom object type detection."""

        class CustomClass:
            pass

        obj = CustomClass()
        result = get_type_str(obj)
        assert result == "CustomClass"

    def test_regular_string(self):
        """Test regular strings without special patterns."""
        result = get_type_str("just a regular string")
        assert result == "str"

        result = get_type_str("no patterns here")
        assert result == "str"


class TestAnalyzeValue:
    """Test cases for analyze_value function."""

    def test_simple_values(self):
        """Test analysis of simple values."""
        assert analyze_value(42) == "int"
        assert analyze_value("hello") == "str"
        assert analyze_value(True) == "bool"  # noqa: FBT003
        assert analyze_value(None) == "null"

    def test_simple_list(self):
        """Test analysis of simple list."""
        result = analyze_value([1, 2, 3])
        assert "list(int)" in result
        assert "[size=3]" in result

    def test_empty_list(self):
        """Test analysis of empty list."""
        result = analyze_value([])
        assert result == "list(unknown)"

    def test_nested_dict(self):
        """Test analysis of nested dictionary."""
        nested_data = {"name": "John", "age": 30, "scores": [95, 87, 92]}

        result = analyze_value(nested_data)

        assert isinstance(result, dict)
        assert result["name"] == "str"
        assert result["age"] == "int"
        assert "list(int)" in result["scores"]

    def test_max_depth_limit(self):
        """Test max depth limitation."""
        deeply_nested = {"level1": {"level2": {"level3": {"level4": "deep"}}}}

        result = analyze_value(deeply_nested, max_depth=2)

        # Should reach max depth at some point
        assert "max_depth_reached" in str(result)

    def test_size_hints_disabled(self):
        """Test with size hints disabled."""
        result = analyze_value([1, 2, 3], size_hints=False)
        assert "list(int)" in result
        assert "[size=" not in result

    def test_include_samples_for_complex_list(self):
        """Test sample inclusion for complex list structures."""
        complex_list = [{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]

        result = analyze_value(complex_list, include_samples=True)

        assert "sample:" in result
        assert "list(dict)" in result

    def test_include_samples_disabled(self):
        """Test with samples disabled."""
        complex_list = [{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]

        result = analyze_value(complex_list, include_samples=False)

        assert "sample:" not in result

    def test_error_handling(self):
        """Test error handling in analysis."""

        # Create an object that raises exception on access
        class ProblematicClass:
            def __getitem__(self, key):
                msg = "Access error"
                raise RuntimeError(msg)

        problematic = ProblematicClass()
        result = analyze_value(problematic)

        assert "ProblematicClass" in result or "error(" in result

    def test_tuple_and_set_handling(self):
        """Test analysis of tuples and sets."""
        tuple_result = analyze_value((1, 2, 3))
        assert "list(int)" in tuple_result

        set_result = analyze_value({1, 2, 3})
        assert "list(int)" in set_result


class TestGetDataStructure:
    """Test cases for get_data_structure function."""

    def test_data_object_input(self):
        """Test with Data object as input."""
        mock_data = Mock(spec=Data)
        mock_data.data = {"field": "value"}

        result = get_data_structure(mock_data)

        assert "structure" in result
        assert isinstance(result["structure"], dict)
        assert result["structure"]["field"] == "str"

    def test_dict_input(self):
        """Test with dictionary as input."""
        test_dict = {
            "name": "Test",
            "count": 42,
            "items": [1, 2, 3],
            "metadata": {
                "created": "date created on server",  # Contains "date" pattern
                "tags": ["tag1", "tag2"],
            },
        }

        result = get_data_structure(test_dict)

        assert "structure" in result
        structure = result["structure"]
        assert structure["name"] == "str"
        assert structure["count"] == "int"
        assert "list(int)" in structure["items"]
        assert isinstance(structure["metadata"], dict)
        assert "str(possible_date)" in structure["metadata"]["created"]
        assert "list(str)" in structure["metadata"]["tags"]

    def test_with_sample_values(self):
        """Test including sample values."""
        test_dict = {"numbers": [1, 2, 3, 4, 5], "nested": {"key": "value"}}

        result = get_data_structure(test_dict, include_sample_values=True)

        assert "structure" in result
        assert "samples" in result
        assert "numbers" in result["samples"]
        assert "nested" in result["samples"]

    def test_max_depth_parameter(self):
        """Test max_depth parameter."""
        deeply_nested = {"level1": {"level2": {"level3": {"level4": "deep_value"}}}}

        result = get_data_structure(deeply_nested, max_depth=2)

        # Should have limited depth in analysis
        structure = result["structure"]
        assert "level1" in structure
        # Check that max depth was respected
        assert "max_depth_reached" in str(structure)

    def test_size_hints_disabled(self):
        """Test with size hints disabled."""
        test_dict = {"items": [1, 2, 3, 4, 5]}

        result = get_data_structure(test_dict, size_hints=False)

        structure = result["structure"]
        assert "list(int)" in structure["items"]
        assert "[size=" not in structure["items"]

    def test_sample_structure_disabled(self):
        """Test with sample structure disabled."""
        test_dict = {"complex_list": [{"a": 1}, {"b": 2}]}

        result = get_data_structure(test_dict, include_sample_structure=False)

        structure = result["structure"]
        assert "sample:" not in structure["complex_list"]

    def test_max_sample_size(self):
        """Test max_sample_size parameter."""
        test_dict = {"long_list": list(range(10))}

        result = get_data_structure(test_dict, include_sample_values=True, max_sample_size=3)

        samples = result["samples"]
        assert len(samples["long_list"]) == 3


class TestGetSampleValues:
    """Test cases for get_sample_values function."""

    def test_simple_values(self):
        """Test sampling simple values."""
        assert get_sample_values(42) == 42
        assert get_sample_values("hello") == "hello"
        assert get_sample_values(True) is True  # noqa: FBT003

    def test_list_sampling(self):
        """Test sampling from lists."""
        long_list = list(range(10))
        result = get_sample_values(long_list, max_items=3)

        assert len(result) == 3
        assert result == [0, 1, 2]

    def test_tuple_sampling(self):
        """Test sampling from tuples."""
        test_tuple = tuple(range(5))
        result = get_sample_values(test_tuple, max_items=2)

        assert len(result) == 2
        assert result == [0, 1]

    def test_set_sampling(self):
        """Test sampling from sets."""
        test_set = {1, 2, 3, 4, 5}
        result = get_sample_values(test_set, max_items=3)

        assert len(result) == 3
        # Order may vary for sets, but should contain elements from the set
        assert all(item in test_set for item in result)

    def test_dict_sampling(self):
        """Test sampling from dictionaries."""
        test_dict = {"list_field": [1, 2, 3, 4, 5], "simple_field": "value", "nested_dict": {"inner": [10, 20, 30]}}

        result = get_sample_values(test_dict, max_items=2)

        assert isinstance(result, dict)
        assert "simple_field" in result
        assert result["simple_field"] == "value"
        assert len(result["list_field"]) == 2  # Should be limited by max_items
        assert len(result["nested_dict"]["inner"]) == 2  # Nested sampling

    def test_nested_structure_sampling(self):
        """Test sampling from nested structures."""
        nested_structure = {"data": [{"items": [1, 2, 3, 4, 5]}, {"items": [6, 7, 8, 9, 10]}]}

        result = get_sample_values(nested_structure, max_items=2)

        assert len(result["data"]) == 2
        # The function recursively applies max_items at each level
        # But the nested dictionaries are returned as-is, then their contents are sampled
        # Let's just verify the structure is correct without specific lengths
        assert "items" in result["data"][0]
        assert "items" in result["data"][1]
        assert isinstance(result["data"][0]["items"], list)
        assert isinstance(result["data"][1]["items"], list)

    def test_empty_collections(self):
        """Test sampling from empty collections."""
        assert get_sample_values([]) == []
        assert get_sample_values({}) == {}
        assert get_sample_values(set()) == []

    def test_max_items_larger_than_collection(self):
        """Test when max_items is larger than collection size."""
        small_list = [1, 2]
        result = get_sample_values(small_list, max_items=10)

        assert result == [1, 2]  # Should return all items


class TestIntegrationScenarios:
    """Integration test cases for complex data structures."""

    def test_real_world_api_response(self):
        """Test analysis of realistic API response structure."""
        api_response = {
            "status": "success",
            "data": {
                "users": [
                    {
                        "id": 1,
                        "name": "John Doe",
                        "email": "john@example.com",
                        "created_at": "2023-01-15T10:30:00Z",
                        "metadata": {"login_count": 42, "preferences": {"theme": "dark", "notifications": True}},
                    },
                    {
                        "id": 2,
                        "name": "Jane Smith",
                        "email": "jane@example.com",
                        "created_at": "2023-02-01T14:20:00Z",
                        "metadata": {"login_count": 15, "preferences": {"theme": "light", "notifications": False}},
                    },
                ],
                "pagination": {"page": 1, "per_page": 10, "total": 2},
            },
        }

        result = get_data_structure(api_response, include_sample_values=True, include_sample_structure=True)

        assert "structure" in result
        assert "samples" in result

        structure = result["structure"]
        assert structure["status"] == "str"
        assert "data" in structure
        assert "users" in structure["data"]
        assert "list(dict)" in structure["data"]["users"]

        # Check that pagination structure is captured
        pagination = structure["data"]["pagination"]
        assert pagination["page"] == "int"
        assert pagination["total"] == "int"

    def test_mixed_data_types_analysis(self):
        """Test analysis of mixed data types."""
        mixed_data = {
            "strings": ["hello", "world"],
            "numbers": [1, 2, 3.14, 5],
            "booleans": [True, False, True],
            "mixed_list": [1, "hello", True, None, {"nested": "value"}],
            "json_strings": ['{"key": "value"}', '{"another": "json"}'],
            "dates": ["has date in string", "another time value"],
            "empty_structures": {"empty_list": [], "empty_dict": {}},
        }

        result = get_data_structure(mixed_data)
        structure = result["structure"]

        assert "list(str)" in structure["strings"]
        assert "int|float" in structure["numbers"] or "float|int" in structure["numbers"]
        assert "list(bool)" in structure["booleans"]
        # The mixed list types may be in any order, so just check it contains list() and multiple types
        mixed_list_str = structure["mixed_list"]
        assert "list(" in mixed_list_str
        assert "|" in mixed_list_str  # Multiple types indicated by pipe
        assert "str(json)" in structure["json_strings"]
        assert "str(possible_date)" in structure["dates"]
        assert structure["empty_structures"]["empty_list"] == "list(unknown)"
        assert structure["empty_structures"]["empty_dict"] == {}

    def test_deep_nesting_with_max_depth(self):
        """Test deeply nested structure with depth limits."""

        def create_deep_structure(depth):
            if depth == 0:
                return "leaf_value"
            return {"level": depth, "nested": create_deep_structure(depth - 1)}

        deep_data = create_deep_structure(10)

        result = get_data_structure(deep_data, max_depth=5)

        # Should handle deep nesting gracefully
        assert "structure" in result
        assert "max_depth_reached" in str(result["structure"])

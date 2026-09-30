"""Tests for the types_compatible function and TYPE_MIGRATIONS constant.

Validates that the Data->JSON and DataFrame->Table type rename migration
works correctly for edge compatibility checking.
"""

from __future__ import annotations

from lfx.graph.edge.base import TYPE_MIGRATIONS, types_compatible

# --- Named constants to avoid magic values ---

# Old type names (pre-migration)
OLD_DATA_TYPE = "Data"
OLD_DATAFRAME_TYPE = "DataFrame"

# New type names (post-migration)
NEW_JSON_TYPE = "JSON"
NEW_TABLE_TYPE = "Table"

# Types that are NOT part of any migration
MESSAGE_TYPE = "Message"
TEXT_TYPE = "Text"
CUSTOM_TYPE = "CustomType"
ANOTHER_CUSTOM_TYPE = "AnotherCustomType"

# Invalid / adversarial type strings
LOWERCASE_DATA = "data"
LOWERCASE_JSON = "json"
PARTIAL_DATA = "Dat"
EMPTY_STRING_TYPE = ""


class TestTypeMigrationsConstant:
    """Verify the TYPE_MIGRATIONS dict is correctly defined."""

    def test_should_map_data_to_json(self):
        assert TYPE_MIGRATIONS[OLD_DATA_TYPE] == NEW_JSON_TYPE

    def test_should_map_dataframe_to_table(self):
        assert TYPE_MIGRATIONS[OLD_DATAFRAME_TYPE] == NEW_TABLE_TYPE

    def test_should_contain_exactly_two_entries(self):
        assert len(TYPE_MIGRATIONS) == 2


class TestTypesCompatibleSuccessCases:
    """Tests for cases where types SHOULD be compatible."""

    def test_should_be_compatible_when_old_output_matches_old_input(self):
        # Arrange
        output_types = [OLD_DATA_TYPE]
        input_types = [OLD_DATA_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is True

    def test_should_be_compatible_when_new_output_matches_new_input(self):
        # Arrange
        output_types = [NEW_JSON_TYPE]
        input_types = [NEW_JSON_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is True

    def test_should_be_compatible_when_old_output_matches_new_input(self):
        # Arrange: Data output connecting to a JSON input
        output_types = [OLD_DATA_TYPE]
        input_types = [NEW_JSON_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is True

    def test_should_be_compatible_when_new_output_matches_old_input(self):
        # Arrange: JSON output connecting to a Data input
        output_types = [NEW_JSON_TYPE]
        input_types = [OLD_DATA_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is True

    def test_should_be_compatible_when_dataframe_output_matches_table_input(self):
        # Arrange
        output_types = [OLD_DATAFRAME_TYPE]
        input_types = [NEW_TABLE_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is True

    def test_should_be_compatible_when_table_output_matches_dataframe_input(self):
        # Arrange
        output_types = [NEW_TABLE_TYPE]
        input_types = [OLD_DATAFRAME_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is True

    def test_should_be_compatible_when_non_migrated_types_match(self):
        # Arrange: Message->Message, no migration involved
        output_types = [MESSAGE_TYPE]
        input_types = [MESSAGE_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is True

    def test_should_be_compatible_when_any_output_matches_any_input(self):
        # Arrange: Multiple types in both lists, one pair matches
        output_types = [TEXT_TYPE, OLD_DATA_TYPE]
        input_types = [MESSAGE_TYPE, NEW_JSON_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert: Data->JSON migration makes this compatible
        assert result is True


class TestTypesCompatibleNegativeCases:
    """Tests for cases where types should NOT be compatible."""

    def test_should_not_be_compatible_when_types_completely_different(self):
        # Arrange: Data and Message are unrelated
        output_types = [OLD_DATA_TYPE]
        input_types = [MESSAGE_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is False

    def test_should_not_be_compatible_when_json_vs_table(self):
        # Arrange: JSON and Table are different migration families
        output_types = [NEW_JSON_TYPE]
        input_types = [NEW_TABLE_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is False

    def test_should_not_be_compatible_when_data_vs_dataframe(self):
        # Arrange: Data and DataFrame are from different migration families
        output_types = [OLD_DATA_TYPE]
        input_types = [OLD_DATAFRAME_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is False

    def test_should_not_be_compatible_when_data_vs_table(self):
        # Arrange: Data (->JSON) should not match Table
        output_types = [OLD_DATA_TYPE]
        input_types = [NEW_TABLE_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is False

    def test_should_not_be_compatible_when_dataframe_vs_json(self):
        # Arrange: DataFrame (->Table) should not match JSON
        output_types = [OLD_DATAFRAME_TYPE]
        input_types = [NEW_JSON_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is False


class TestTypesCompatibleEdgeCases:
    """Tests for boundary and edge conditions."""

    def test_should_not_be_compatible_when_both_lists_empty(self):
        # Arrange
        output_types: list[str] = []
        input_types: list[str] = []

        # Act
        result = types_compatible(output_types, input_types)

        # Assert: No types to match means not compatible
        assert result is False

    def test_should_not_be_compatible_when_output_types_empty(self):
        # Arrange
        output_types: list[str] = []
        input_types = [NEW_JSON_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is False

    def test_should_not_be_compatible_when_input_types_empty(self):
        # Arrange
        output_types = [OLD_DATA_TYPE]
        input_types: list[str] = []

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is False

    def test_should_be_compatible_with_single_match_in_large_lists(self):
        # Arrange: Many non-matching types but one match buried in the lists
        output_types = [TEXT_TYPE, CUSTOM_TYPE, "TypeA", "TypeB", OLD_DATAFRAME_TYPE]
        input_types = ["TypeC", "TypeD", "TypeE", MESSAGE_TYPE, NEW_TABLE_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert: DataFrame->Table migration makes this compatible
        assert result is True

    def test_should_handle_unknown_types_without_migration(self):
        # Arrange: Types not in TYPE_MIGRATIONS should still match directly
        output_types = [CUSTOM_TYPE]
        input_types = [CUSTOM_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is True

    def test_should_not_match_unknown_types_that_differ(self):
        # Arrange: Two different unknown types
        output_types = [CUSTOM_TYPE]
        input_types = [ANOTHER_CUSTOM_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is False

    def test_should_not_crash_with_empty_string_types(self):
        # Arrange: Empty strings as types
        output_types = [EMPTY_STRING_TYPE]
        input_types = [EMPTY_STRING_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert: Empty strings match each other (direct equality)
        assert result is True

    def test_should_not_match_empty_string_vs_real_type(self):
        # Arrange
        output_types = [EMPTY_STRING_TYPE]
        input_types = [OLD_DATA_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is False


class TestTypesCompatibleAdversarialCases:
    """Tests for adversarial / tricky inputs."""

    def test_should_not_match_case_sensitive_types(self):
        # Arrange: "data" (lowercase) should NOT match "Data" (capitalized)
        output_types = [LOWERCASE_DATA]
        input_types = [OLD_DATA_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert: Type matching is case-sensitive
        assert result is False

    def test_should_not_match_lowercase_json_vs_uppercase(self):
        # Arrange: "json" should NOT match "JSON"
        output_types = [LOWERCASE_JSON]
        input_types = [NEW_JSON_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is False

    def test_should_not_match_partial_type_names(self):
        # Arrange: "Dat" should NOT match "Data"
        output_types = [PARTIAL_DATA]
        input_types = [OLD_DATA_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is False

    def test_should_be_compatible_when_mixed_old_and_new_in_same_list(self):
        # Arrange: A list containing both old and new names
        output_types = [OLD_DATA_TYPE, NEW_TABLE_TYPE]
        input_types = [NEW_JSON_TYPE, OLD_DATAFRAME_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert: Data->JSON migration matches, and Table->DataFrame migration matches
        assert result is True

    def test_should_not_match_reversed_migration_families(self):
        # Arrange: JSON output should not match DataFrame input
        output_types = [NEW_JSON_TYPE]
        input_types = [OLD_DATAFRAME_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is False

    def test_should_not_match_table_vs_data(self):
        # Arrange: Table output should not match Data input
        output_types = [NEW_TABLE_TYPE]
        input_types = [OLD_DATA_TYPE]

        # Act
        result = types_compatible(output_types, input_types)

        # Assert
        assert result is False

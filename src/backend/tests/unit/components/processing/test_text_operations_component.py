"""Tests for TextOperations component.

Includes regression tests for QA-reported bugs.
"""

import pytest
from lfx.components.processing.text_operations import TextOperations
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


class TestTextOperationsComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return TextOperations

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "text_input": "Hello world",
            "operation": [{"name": "Word Count"}],
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []


class TestTextOperationsWordCount:
    def test_word_count_basic(self):
        """Test basic word count operation."""
        component = TextOperations()
        component.text_input = "Hello world this is a test"
        component.count_words = True
        component.count_characters = True
        component.count_lines = True

        result = component._word_count(component.text_input)

        assert result["word_count"] == 6
        assert result["unique_words"] == 6
        assert result["character_count"] == 26
        assert result["character_count_no_spaces"] == 21
        assert result["line_count"] == 1
        assert result["non_empty_lines"] == 1

    def test_word_count_multiline(self):
        """Test word count with multiple lines."""
        component = TextOperations()
        component.count_words = True
        component.count_characters = True
        component.count_lines = True

        result = component._word_count("Line one\nLine two\n\nLine four")

        assert result["line_count"] == 4
        assert result["non_empty_lines"] == 3

    def test_word_count_disabled_options(self):
        """Test word count with disabled options."""
        component = TextOperations()
        component.count_words = False
        component.count_characters = False
        component.count_lines = True

        result = component._word_count("Hello world")

        assert "word_count" not in result
        assert "character_count" not in result
        assert "line_count" in result


class TestTextOperationsCaseConversion:
    def test_case_uppercase(self):
        """Test uppercase conversion."""
        component = TextOperations()
        component.case_type = "uppercase"

        result = component._case_conversion("hello world")

        assert result == "HELLO WORLD"

    def test_case_lowercase(self):
        """Test lowercase conversion."""
        component = TextOperations()
        component.case_type = "lowercase"

        result = component._case_conversion("HELLO WORLD")

        assert result == "hello world"

    def test_case_title(self):
        """Test title case conversion."""
        component = TextOperations()
        component.case_type = "title"

        result = component._case_conversion("hello world")

        assert result == "Hello World"

    def test_case_capitalize(self):
        """Test capitalize conversion."""
        component = TextOperations()
        component.case_type = "capitalize"

        result = component._case_conversion("hello world")

        assert result == "Hello world"

    def test_case_swapcase(self):
        """Test swapcase conversion."""
        component = TextOperations()
        component.case_type = "swapcase"

        result = component._case_conversion("Hello World")

        assert result == "hELLO wORLD"


class TestTextOperationsReplace:
    def test_replace_simple(self):
        """Test simple text replacement."""
        component = TextOperations()
        component.search_pattern = "hello"
        component.replacement_text = "hi"
        component.use_regex = False

        result = component._text_replace("hello world")

        assert result == "hi world"

    def test_replace_multiple_occurrences(self):
        """Test replacement of multiple occurrences."""
        component = TextOperations()
        component.search_pattern = "a"
        component.replacement_text = "X"
        component.use_regex = False

        result = component._text_replace("banana")

        assert result == "bXnXnX"

    def test_replace_regex(self):
        """Test regex replacement."""
        component = TextOperations()
        component.search_pattern = r"\d+"
        component.replacement_text = "NUM"
        component.use_regex = True

        result = component._text_replace("abc123def456")

        assert result == "abcNUMdefNUM"

    def test_replace_empty_pattern(self):
        """Test replacement with empty pattern."""
        component = TextOperations()
        component.search_pattern = ""
        component.replacement_text = "X"
        component.use_regex = False

        result = component._text_replace("hello")

        assert result == "hello"

    def test_replace_invalid_regex(self):
        """Test replacement with invalid regex pattern."""
        component = TextOperations()
        component.search_pattern = "[invalid"
        component.replacement_text = "X"
        component.use_regex = True
        component.log = lambda _: None

        result = component._text_replace("hello")

        assert result == "hello"


class TestTextOperationsExtract:
    def test_extract_numbers(self):
        """Test extracting numbers from text."""
        component = TextOperations()
        component.extract_pattern = r"\d+"
        component.max_matches = 10

        result = component._text_extract("abc123def456ghi789")

        assert result == ["123", "456", "789"]

    def test_extract_with_limit(self):
        """Test extraction with max matches limit."""
        component = TextOperations()
        component.extract_pattern = r"\d+"
        component.max_matches = 2

        result = component._text_extract("abc123def456ghi789")

        assert result == ["123", "456"]

    def test_extract_no_matches(self):
        """Test extraction with no matches."""
        component = TextOperations()
        component.extract_pattern = r"\d+"
        component.max_matches = 10

        result = component._text_extract("no numbers here")

        assert result == []

    def test_extract_empty_pattern(self):
        """Test extraction with empty pattern."""
        component = TextOperations()
        component.extract_pattern = ""
        component.max_matches = 10

        result = component._text_extract("hello")

        assert result == []

    def test_extract_invalid_regex(self):
        """Test extraction with invalid regex raises ValueError (Bug #3 fix)."""
        component = TextOperations()
        component.extract_pattern = "[invalid"
        component.max_matches = 10

        with pytest.raises(ValueError, match="Invalid regex pattern"):
            component._text_extract("hello")


class TestTextOperationsHead:
    def test_head_basic(self):
        """Test extracting head of text."""
        component = TextOperations()
        component.head_characters = 5

        result = component._text_head("Hello World")

        assert result == "Hello"

    def test_head_longer_than_text(self):
        """Test head with length longer than text."""
        component = TextOperations()
        component.head_characters = 100

        result = component._text_head("Hello")

        assert result == "Hello"

    def test_head_zero_characters(self):
        """Test head with zero characters."""
        component = TextOperations()
        component.head_characters = 0

        result = component._text_head("Hello")

        assert result == ""

    def test_head_negative_characters(self):
        """Test head with negative characters raises ValueError (Bug #4 fix)."""
        component = TextOperations()
        component.head_characters = -5

        with pytest.raises(ValueError, match="non-negative"):
            component._text_head("Hello")


class TestTextOperationsTail:
    def test_tail_basic(self):
        """Test extracting tail of text."""
        component = TextOperations()
        component.tail_characters = 5

        result = component._text_tail("Hello World")

        assert result == "World"

    def test_tail_longer_than_text(self):
        """Test tail with length longer than text."""
        component = TextOperations()
        component.tail_characters = 100

        result = component._text_tail("Hello")

        assert result == "Hello"

    def test_tail_zero_characters(self):
        """Test tail with zero characters."""
        component = TextOperations()
        component.tail_characters = 0

        result = component._text_tail("Hello")

        assert result == ""

    def test_tail_negative_characters(self):
        """Test tail with negative characters raises ValueError (Bug #7 fix)."""
        component = TextOperations()
        component.tail_characters = -5

        with pytest.raises(ValueError, match="non-negative"):
            component._text_tail("Hello")


class TestTextOperationsStrip:
    def test_strip_both(self):
        """Test stripping from both sides."""
        component = TextOperations()
        component.strip_mode = "both"
        component.strip_characters = ""

        result = component._text_strip("  hello  ")

        assert result == "hello"

    def test_strip_left(self):
        """Test stripping from left side only."""
        component = TextOperations()
        component.strip_mode = "left"
        component.strip_characters = ""

        result = component._text_strip("  hello  ")

        assert result == "hello  "

    def test_strip_right(self):
        """Test stripping from right side only."""
        component = TextOperations()
        component.strip_mode = "right"
        component.strip_characters = ""

        result = component._text_strip("  hello  ")

        assert result == "  hello"

    def test_strip_specific_characters(self):
        """Test stripping specific characters."""
        component = TextOperations()
        component.strip_mode = "both"
        component.strip_characters = "xy"

        result = component._text_strip("xyhelloyx")

        assert result == "hello"


class TestTextOperationsJoin:
    def test_join_two_texts(self):
        """Test joining two texts."""
        component = TextOperations()
        component.text_input_2 = "world"

        result = component._text_join("hello")

        assert result == "hello\nworld"

    def test_join_empty_first(self):
        """Test joining with empty first text."""
        component = TextOperations()
        component.text_input_2 = "world"

        result = component._text_join("")

        assert result == "world"

    def test_join_empty_second(self):
        """Test joining with empty second text."""
        component = TextOperations()
        component.text_input_2 = ""

        result = component._text_join("hello")

        assert result == "hello"

    def test_join_both_empty(self):
        """Test joining with both texts empty."""
        component = TextOperations()
        component.text_input_2 = ""

        result = component._text_join("")

        assert result == ""


class TestTextOperationsClean:
    def test_clean_extra_spaces(self):
        """Test removing extra spaces."""
        component = TextOperations()
        component.remove_extra_spaces = True
        component.remove_special_chars = False
        component.remove_empty_lines = False

        result = component._text_clean("hello   world")

        assert result == "hello world"

    def test_clean_special_chars(self):
        """Test removing ALL special characters (Bug #10 fix)."""
        component = TextOperations()
        component.remove_extra_spaces = False
        component.remove_special_chars = True
        component.remove_empty_lines = False

        result = component._text_clean("hello@world#test!")

        # All special characters are removed including @ # and !
        assert result == "helloworldtest"
        assert "@" not in result
        assert "#" not in result
        assert "!" not in result

    def test_clean_empty_lines(self):
        """Test removing empty lines."""
        component = TextOperations()
        component.remove_extra_spaces = False
        component.remove_special_chars = False
        component.remove_empty_lines = True

        result = component._text_clean("line1\n\nline2\n\n\nline3")

        assert result == "line1\nline2\nline3"

    def test_clean_all_options(self):
        """Test all cleaning options together."""
        component = TextOperations()
        component.remove_extra_spaces = True
        component.remove_special_chars = True
        component.remove_empty_lines = True

        result = component._text_clean("hello   @world\n\ntest!")

        assert "  " not in result
        assert "@" not in result


class TestTextOperationsToDataFrame:
    def test_dataframe_basic(self):
        """Test basic table to DataFrame conversion."""
        component = TextOperations()
        component.table_separator = "|"
        component.has_header = True
        component.log = lambda _: None

        table = "| Name | Age |\n| John | 25 |\n| Jane | 30 |"
        result = component._text_to_dataframe(table)

        assert isinstance(result, DataFrame)
        assert len(result) == 2
        assert list(result.columns) == ["Name", "Age"]

    def test_dataframe_no_header(self):
        """Test DataFrame conversion without header."""
        component = TextOperations()
        component.table_separator = "|"
        component.has_header = False
        component.log = lambda _: None

        table = "| John | 25 |\n| Jane | 30 |"
        result = component._text_to_dataframe(table)

        assert isinstance(result, DataFrame)
        assert len(result) == 2
        assert "col_0" in result.columns

    def test_dataframe_empty_input(self):
        """Test DataFrame conversion with empty input."""
        component = TextOperations()
        component.table_separator = "|"
        component.has_header = True
        component.log = lambda _: None

        result = component._text_to_dataframe("")

        assert isinstance(result, DataFrame)
        assert len(result) == 0

    def test_dataframe_custom_separator(self):
        """Test DataFrame conversion with custom separator."""
        component = TextOperations()
        component.table_separator = ","
        component.has_header = True
        component.log = lambda _: None

        table = "Name,Age\nJohn,25\nJane,30"
        result = component._text_to_dataframe(table)

        assert isinstance(result, DataFrame)
        assert len(result) == 2


class TestTextOperationsUpdateBuildConfig:
    def test_update_build_config_word_count(self):
        """Test build config update for Word Count operation."""
        component = TextOperations()
        build_config = {
            field: {"show": True}
            for field in ["count_words", "count_characters", "count_lines", "case_type", "search_pattern"]
        }

        result = component.update_build_config(build_config, [{"name": "Word Count"}], "operation")

        assert result["count_words"]["show"] is True
        assert result["count_characters"]["show"] is True
        assert result["count_lines"]["show"] is True
        assert result["case_type"]["show"] is False
        assert result["search_pattern"]["show"] is False

    def test_update_build_config_case_conversion(self):
        """Test build config update for Case Conversion operation."""
        component = TextOperations()
        build_config = {field: {"show": True} for field in ["count_words", "case_type", "search_pattern"]}

        result = component.update_build_config(build_config, [{"name": "Case Conversion"}], "operation")

        assert result["case_type"]["show"] is True
        assert result["count_words"]["show"] is False

    def test_update_build_config_text_replace(self):
        """Test build config update for Text Replace operation."""
        component = TextOperations()
        build_config = {
            field: {"show": True} for field in ["search_pattern", "replacement_text", "use_regex", "case_type"]
        }

        result = component.update_build_config(build_config, [{"name": "Text Replace"}], "operation")

        assert result["search_pattern"]["show"] is True
        assert result["replacement_text"]["show"] is True
        assert result["use_regex"]["show"] is True
        assert result["case_type"]["show"] is False


class TestTextOperationsUpdateOutputs:
    def test_update_outputs_word_count(self):
        """Test output update for Word Count operation."""
        component = TextOperations()
        frontend_node = {"outputs": []}

        result = component.update_outputs(frontend_node, "operation", [{"name": "Word Count"}])

        assert len(result["outputs"]) == 1
        assert result["outputs"][0].name == "data"

    def test_update_outputs_dataframe(self):
        """Test output update for Text to DataFrame operation."""
        component = TextOperations()
        frontend_node = {"outputs": []}

        result = component.update_outputs(frontend_node, "operation", [{"name": "Text to DataFrame"}])

        assert len(result["outputs"]) == 1
        assert result["outputs"][0].name == "dataframe"

    def test_update_outputs_text_join(self):
        """Test output update for Text Join operation."""
        component = TextOperations()
        frontend_node = {"outputs": []}

        result = component.update_outputs(frontend_node, "operation", [{"name": "Text Join"}])

        assert len(result["outputs"]) == 2
        assert result["outputs"][0].name == "text"
        assert result["outputs"][1].name == "message"

    def test_update_outputs_message_operations(self):
        """Test output update for message-returning operations."""
        component = TextOperations()

        for operation in [
            "Case Conversion",
            "Text Replace",
            "Text Extract",
            "Text Head",
            "Text Tail",
            "Text Strip",
            "Text Clean",
        ]:
            frontend_node = {"outputs": []}
            result = component.update_outputs(frontend_node, "operation", [{"name": operation}])

            assert len(result["outputs"]) == 1
            assert result["outputs"][0].name == "message"


class TestTextOperationsOutputMethods:
    def test_get_data_word_count(self):
        """Test get_data method for Word Count."""
        component = TextOperations()
        component.operation = [{"name": "Word Count"}]
        component.text_input = "hello world"
        component.count_words = True
        component.count_characters = True
        component.count_lines = True

        result = component.get_data()

        assert isinstance(result, Data)
        assert "word_count" in result.data

    def test_get_data_non_word_count(self):
        """Test get_data method for non-Word Count operation."""
        component = TextOperations()
        component.operation = [{"name": "Case Conversion"}]
        component.text_input = "hello"

        result = component.get_data()

        assert isinstance(result, Data)
        assert result.data == {}

    def test_get_message(self):
        """Test get_message method."""
        component = TextOperations()
        component.operation = [{"name": "Case Conversion"}]
        component.text_input = "hello"
        component.case_type = "uppercase"

        result = component.get_message()

        assert isinstance(result, Message)
        assert result.text == "HELLO"

    def test_get_dataframe(self):
        """Test get_dataframe method."""
        component = TextOperations()
        component.operation = [{"name": "Text to DataFrame"}]
        component.text_input = "| A | B |\n| 1 | 2 |"
        component.table_separator = "|"
        component.has_header = True
        component.log = lambda _: None

        result = component.get_dataframe()

        assert isinstance(result, DataFrame)

    def test_get_text(self):
        """Test get_text method."""
        component = TextOperations()
        component.operation = [{"name": "Text Join"}]
        component.text_input = "hello"
        component.text_input_2 = "world"

        result = component.get_text()

        assert isinstance(result, Message)
        assert result.text == "hello\nworld"


# ============================================================================
# Bug Regression Tests
# These tests ensure reported bugs remain fixed and don't regress.
# ============================================================================


class TestBugFixWordCountEmptyText:
    """Bug #2: Word Count should return zeros for empty text."""

    def test_word_count_empty_string_returns_zeros(self):
        """Empty text should return all zeros, not non-zero values."""
        component = TextOperations()
        component.count_words = True
        component.count_characters = True
        component.count_lines = True

        result = component._word_count("")

        assert result["word_count"] == 0
        assert result["unique_words"] == 0
        assert result["character_count"] == 0
        assert result["character_count_no_spaces"] == 0
        assert result["line_count"] == 0
        assert result["non_empty_lines"] == 0

    def test_word_count_whitespace_only_returns_zeros(self):
        """Whitespace-only text should return zeros."""
        component = TextOperations()
        component.count_words = True
        component.count_characters = True
        component.count_lines = True

        result = component._word_count("   \n\t\n   ")

        assert result["word_count"] == 0
        assert result["unique_words"] == 0
        assert result["character_count"] == 0
        assert result["character_count_no_spaces"] == 0
        assert result["line_count"] == 0
        assert result["non_empty_lines"] == 0

    def test_process_text_allows_empty_for_word_count(self):
        """process_text should allow empty text for Word Count operation."""
        component = TextOperations()
        component.text_input = ""
        component.operation = [{"name": "Word Count"}]
        component.count_words = True
        component.count_characters = True
        component.count_lines = True

        result = component.process_text()

        assert result is not None
        assert result["word_count"] == 0


class TestBugFixTextJoinEmptyFirst:
    """Bug #9: Text Join should return second text when first is empty."""

    def test_process_text_allows_empty_for_text_join(self):
        """process_text should allow empty first text for Text Join."""
        component = TextOperations()
        component.text_input = ""
        component.operation = [{"name": "Text Join"}]
        component.text_input_2 = "world"

        result = component.process_text()

        assert result == "world"


class TestBugFixTextStripTabs:
    """Bug #8: Text Strip should remove tab characters."""

    def test_strip_removes_tabs(self):
        """Strip should remove tabs when using default whitespace stripping."""
        component = TextOperations()
        component.strip_mode = "both"
        component.strip_characters = ""

        result = component._text_strip("\t\thello world\t\t")

        assert result == "hello world"

    def test_strip_removes_mixed_whitespace(self):
        """Strip should remove all whitespace types including tabs and newlines."""
        component = TextOperations()
        component.strip_mode = "both"
        component.strip_characters = ""

        result = component._text_strip("\n\t  hello world  \t\n")

        assert result == "hello world"


class TestBugFixDataFrameHeaderValidation:
    """Bug #11: DataFrame should validate header column count matches data."""

    def test_header_column_mismatch_raises_error(self):
        """Mismatched header/data columns should raise clear error."""
        component = TextOperations()

        rows = [
            ["Name Age City"],  # 1 column (malformed header)
            ["John", "30", "NYC"],  # 3 columns
        ]

        with pytest.raises(ValueError, match="Header mismatch"):
            component._create_dataframe(rows, has_header=True)

    def test_error_message_includes_column_counts(self):
        """Error message should include both column counts."""
        component = TextOperations()

        rows = [
            ["Name"],  # 1 column
            ["John", "30"],  # 2 columns
        ]

        with pytest.raises(ValueError, match=r"1 column\(s\) in header.*2 column\(s\) in data"):
            component._create_dataframe(rows, has_header=True)


class TestBugFixInputValidation:
    """Tests for input validation improvements."""

    def test_head_characters_has_range_spec(self):
        """head_characters should have range_spec with min=0."""
        component = TextOperations()

        head_input = next(
            (inp for inp in component.inputs if inp.name == "head_characters"),
            None,
        )

        assert head_input is not None
        assert head_input.range_spec is not None
        assert head_input.range_spec.min == 0

    def test_tail_characters_has_range_spec(self):
        """tail_characters should have range_spec with min=0."""
        component = TextOperations()

        tail_input = next(
            (inp for inp in component.inputs if inp.name == "tail_characters"),
            None,
        )

        assert tail_input is not None
        assert tail_input.range_spec is not None
        assert tail_input.range_spec.min == 0

    def test_text_input_uses_message_text_input(self):
        """Bug #1: text_input should use MessageTextInput type."""
        component = TextOperations()

        text_input = next(
            (inp for inp in component.inputs if inp.name == "text_input"),
            None,
        )

        assert text_input is not None
        # MessageTextInput is the correct type for variable input support
        assert text_input.name == "text_input"

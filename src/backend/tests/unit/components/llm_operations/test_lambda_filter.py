from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.components.llm_operations.lambda_filter import LambdaFilterComponent
from lfx.schema import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


class TestLambdaFilterComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return LambdaFilterComponent

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM that works with async invoke."""
        mock = AsyncMock()
        mock.ainvoke = AsyncMock()
        return mock

    @pytest.fixture
    def model_metadata(self):
        """Helper fixture that returns standard model metadata structure."""
        return [
            {
                "name": "gpt-3.5-turbo",
                "provider": "OpenAI",
                "metadata": {
                    "model_class": "MockLanguageModel",
                    "model_name_param": "model",
                    "api_key_param": "api_key",
                },
            }
        ]

    @pytest.fixture
    def default_kwargs(self, model_metadata):
        """Return the default kwargs for the component with proper model metadata."""
        return {
            "data": [Data(data={"items": [{"name": "test1", "value": 10}, {"name": "test2", "value": 20}]})],
            "model": model_metadata,
            "api_key": "test-api-key",
            "filter_instruction": "Filter items with value greater than 15",
            "sample_size": 1000,
            "max_size": 30000,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []


class TestValidateLambda(TestLambdaFilterComponent):
    """Tests for _validate_lambda method."""

    def test_should_return_true_when_lambda_is_valid(self, component_class):
        # Arrange
        component = component_class()
        valid_lambda = "lambda x: x + 1"

        # Act
        result = component._validate_lambda(valid_lambda)

        # Assert
        assert result is True

    def test_should_return_false_when_lambda_keyword_missing(self, component_class):
        # Arrange
        component = component_class()
        invalid_lambda = "x: x + 1"

        # Act
        result = component._validate_lambda(invalid_lambda)

        # Assert
        assert result is False

    def test_should_return_false_when_colon_missing(self, component_class):
        # Arrange
        component = component_class()
        invalid_lambda = "lambda x x + 1"

        # Act
        result = component._validate_lambda(invalid_lambda)

        # Assert
        assert result is False

    def test_should_return_true_when_lambda_has_whitespace(self, component_class):
        # Arrange
        component = component_class()
        valid_lambda = "  lambda x: x + 1  "

        # Act
        result = component._validate_lambda(valid_lambda)

        # Assert
        assert result is True


class TestGetDataStructure(TestLambdaFilterComponent):
    """Tests for get_data_structure method."""

    def test_should_return_type_name_when_input_is_primitive(self, component_class):
        # Arrange
        component = component_class()
        bool_value = True

        # Act & Assert
        assert component.get_data_structure("test") == "str"
        assert component.get_data_structure(42) == "int"
        assert component.get_data_structure(3.14) == "float"
        assert component.get_data_structure(bool_value) == "bool"

    def test_should_return_dict_structure_when_input_is_dict(self, component_class):
        # Arrange
        component = component_class()
        test_data = {"key": "value", "number": 42}

        # Act
        result = component.get_data_structure(test_data)

        # Assert
        assert result == {"key": "str", "number": "int"}

    def test_should_return_list_structure_when_input_is_list(self, component_class):
        # Arrange
        component = component_class()
        test_data = [1, 2, 3]

        # Act
        result = component.get_data_structure(test_data)

        # Assert
        assert result == ["int"]

    def test_should_return_empty_list_when_input_is_empty_list(self, component_class):
        # Arrange
        component = component_class()

        # Act
        result = component.get_data_structure([])

        # Assert
        assert result == []

    def test_should_return_nested_structure_when_input_is_nested(self, component_class):
        # Arrange
        component = component_class()
        test_data = {"nested": {"a": [{"b": 1}]}}

        # Act
        result = component.get_data_structure(test_data)

        # Assert
        assert result == {"nested": {"a": [{"b": "int"}]}}


class TestGetInputTypeName(TestLambdaFilterComponent):
    """Tests for _get_input_type_name method."""

    def test_should_return_message_when_input_is_single_message(self, component_class):
        # Arrange
        component = component_class()
        component.data = Message(text="test")

        # Act
        result = component._get_input_type_name()

        # Assert
        assert result == "Message"

    def test_should_return_message_when_input_is_list_of_messages(self, component_class):
        # Arrange
        component = component_class()
        component.data = [Message(text="test1"), Message(text="test2")]

        # Act
        result = component._get_input_type_name()

        # Assert
        assert result == "Message"

    def test_should_return_dataframe_when_input_is_dataframe(self, component_class):
        # Arrange
        component = component_class()
        component.data = DataFrame([{"a": 1}])

        # Act
        result = component._get_input_type_name()

        # Assert
        assert result == "DataFrame"

    def test_should_return_data_when_input_is_data(self, component_class):
        # Arrange
        component = component_class()
        component.data = Data(data={"key": "value"})

        # Act
        result = component._get_input_type_name()

        # Assert
        assert result == "Data"

    def test_should_return_unknown_when_input_is_empty_list(self, component_class):
        # Arrange
        component = component_class()
        component.data = []

        # Act
        result = component._get_input_type_name()

        # Assert
        assert result == "unknown"


class TestIsMessageInput(TestLambdaFilterComponent):
    """Tests for _is_message_input method."""

    def test_should_return_true_when_input_is_single_message(self, component_class):
        # Arrange
        component = component_class()
        component.data = Message(text="test")

        # Act
        result = component._is_message_input()

        # Assert
        assert result is True

    def test_should_return_true_when_input_is_list_of_messages(self, component_class):
        # Arrange
        component = component_class()
        component.data = [Message(text="test1"), Message(text="test2")]

        # Act
        result = component._is_message_input()

        # Assert
        assert result is True

    def test_should_return_false_when_input_is_data(self, component_class):
        # Arrange
        component = component_class()
        component.data = Data(data={"key": "value"})

        # Act
        result = component._is_message_input()

        # Assert
        assert result is False

    def test_should_return_false_when_input_is_empty_list(self, component_class):
        # Arrange
        component = component_class()
        component.data = []

        # Act
        result = component._is_message_input()

        # Assert
        assert result is False


class TestExtractMessageText(TestLambdaFilterComponent):
    """Tests for _extract_message_text method."""

    def test_should_return_text_when_input_is_single_message(self, component_class):
        # Arrange
        component = component_class()
        component.data = Message(text="Hello World")

        # Act
        result = component._extract_message_text()

        # Assert
        assert result == "Hello World"

    def test_should_return_empty_string_when_message_text_is_none(self, component_class):
        # Arrange
        component = component_class()
        component.data = Message(text=None)

        # Act
        result = component._extract_message_text()

        # Assert
        assert result == ""

    def test_should_join_texts_when_input_is_list_of_messages(self, component_class):
        # Arrange
        component = component_class()
        component.data = [Message(text="Hello"), Message(text="World")]

        # Act
        result = component._extract_message_text()

        # Assert
        assert result == "Hello\n\nWorld"

    def test_should_return_single_text_when_list_has_one_message(self, component_class):
        # Arrange
        component = component_class()
        component.data = [Message(text="Only one")]

        # Act
        result = component._extract_message_text()

        # Assert
        assert result == "Only one"


class TestExtractStructuredData(TestLambdaFilterComponent):
    """Tests for _extract_structured_data method."""

    def test_should_return_dict_when_input_is_single_data(self, component_class):
        # Arrange
        component = component_class()
        component.data = Data(data={"key": "value"})

        # Act
        result = component._extract_structured_data()

        # Assert
        assert result == {"key": "value"}

    def test_should_return_records_when_input_is_dataframe(self, component_class):
        # Arrange
        component = component_class()
        component.data = DataFrame([{"a": 1}, {"a": 2}])

        # Act
        result = component._extract_structured_data()

        # Assert
        assert result == [{"a": 1}, {"a": 2}]

    def test_should_combine_data_when_input_is_list_of_data(self, component_class):
        # Arrange
        component = component_class()
        component.data = [Data(data={"a": 1}), Data(data={"b": 2})]

        # Act
        result = component._extract_structured_data()

        # Assert
        assert result == [{"a": 1}, {"b": 2}]

    def test_should_unwrap_single_dict_when_list_has_one_item(self, component_class):
        # Arrange
        component = component_class()
        component.data = [Data(data={"only": "one"})]

        # Act
        result = component._extract_structured_data()

        # Assert
        assert result == {"only": "one"}

    def test_should_return_empty_dict_when_no_data_extracted(self, component_class):
        # Arrange
        component = component_class()
        component.data = []

        # Act
        result = component._extract_structured_data()

        # Assert
        assert result == {}


class TestBuildTextPrompt(TestLambdaFilterComponent):
    """Tests for _build_text_prompt method."""

    def test_should_include_full_text_when_text_is_small(self, component_class):
        # Arrange
        component = component_class()
        component.max_size = 1000
        component.sample_size = 100
        component.filter_instruction = "Transform to uppercase"
        text = "Short text"

        # Act
        result = component._build_text_prompt(text)

        # Assert
        assert "Short text" in result
        assert "Transform to uppercase" in result

    def test_should_truncate_text_when_text_is_large(self, component_class):
        # Arrange
        component = component_class()
        component.max_size = 50
        component.sample_size = 10
        component.filter_instruction = "Summarize"
        text = "A" * 100

        # Act
        result = component._build_text_prompt(text)

        # Assert
        assert "Text length: 100 characters" in result
        assert "First 10 characters" in result
        assert "Last 10 characters" in result


class TestBuildDataPrompt(TestLambdaFilterComponent):
    """Tests for _build_data_prompt method."""

    def test_should_include_full_data_when_data_is_small(self, component_class):
        # Arrange
        component = component_class()
        component.max_size = 1000
        component.sample_size = 100
        component.filter_instruction = "Filter by value"
        data = {"key": "value"}

        # Act
        result = component._build_data_prompt(data)

        # Assert
        assert '"key":"value"' in result or '"key": "value"' in result
        assert "Filter by value" in result

    def test_should_truncate_data_when_data_is_large(self, component_class):
        # Arrange
        component = component_class()
        component.max_size = 50
        component.sample_size = 10
        component.filter_instruction = "Filter"
        data = {"key": "A" * 100}

        # Act
        result = component._build_data_prompt(data)

        # Assert
        assert "Data is too long to display" in result
        assert "First lines (head)" in result
        assert "Last lines (tail)" in result

    def test_should_include_data_structure_in_prompt(self, component_class):
        # Arrange
        component = component_class()
        component.max_size = 10000
        component.sample_size = 100
        component.filter_instruction = "Filter items"
        data = {"items": [{"id": 1}, {"id": 2}]}

        # Act
        result = component._build_data_prompt(data)

        # Assert
        assert '"items"' in result
        assert "Data Structure" in result


class TestNormalizeHttpApiData(TestLambdaFilterComponent):
    """Tests for _normalize_http_api_data method."""

    def test_should_transform_result_key_to_results_when_result_is_list(self, component_class):
        # Arrange
        component = component_class()
        data = {"result": [{"id": 1}, {"id": 2}]}

        # Act
        result = component._normalize_http_api_data(data)

        # Assert
        assert "_results" in result
        assert "result" not in result
        assert result["_results"] == [{"id": 1}, {"id": 2}]

    def test_should_not_transform_result_when_result_is_not_list(self, component_class):
        # Arrange
        component = component_class()
        data = {"result": "string_value"}

        # Act
        result = component._normalize_http_api_data(data)

        # Assert
        assert "result" in result
        assert "_results" not in result
        assert result["result"] == "string_value"

    def test_should_not_transform_data_when_result_key_is_absent(self, component_class):
        # Arrange
        component = component_class()
        data = {"items": [{"id": 1}, {"id": 2}]}

        # Act
        result = component._normalize_http_api_data(data)

        # Assert
        assert "items" in result
        assert "_results" not in result

    def test_should_preserve_list_contents_when_transforming_result(self, component_class):
        # Arrange
        component = component_class()
        data = {"result": [{"name": "test1", "value": 10}, {"name": "test2", "value": 20}]}

        # Act
        result = component._normalize_http_api_data(data)

        # Assert
        assert result["_results"][0]["name"] == "test1"
        assert result["_results"][1]["value"] == 20

    def test_should_return_list_unchanged(self, component_class):
        # Arrange
        component = component_class()
        data = [{"id": 1}, {"id": 2}]

        # Act
        result = component._normalize_http_api_data(data)

        # Assert
        assert result == [{"id": 1}, {"id": 2}]

    def test_should_handle_empty_result_list(self, component_class):
        # Arrange
        component = component_class()
        data = {"result": []}

        # Act
        result = component._normalize_http_api_data(data)

        # Assert
        assert "_results" in result
        assert result["_results"] == []


class TestParseLambdaFromResponse(TestLambdaFilterComponent):
    """Tests for _parse_lambda_from_response method."""

    def test_should_return_callable_when_response_contains_valid_lambda(self, component_class):
        # Arrange
        component = component_class()
        response_text = "lambda x: x + 1"

        # Act
        result = component._parse_lambda_from_response(response_text)

        # Assert
        assert callable(result)
        assert result(5) == 6

    def test_should_extract_lambda_when_response_has_surrounding_text(self, component_class):
        # Arrange
        component = component_class()
        response_text = "Here is the function:\nlambda x: x * 2\nThis will double the value."

        # Act
        result = component._parse_lambda_from_response(response_text)

        # Assert
        assert callable(result)
        assert result(3) == 6

    def test_should_raise_error_when_response_has_no_lambda(self, component_class):
        # Arrange
        component = component_class()
        response_text = "def transform(x): return x + 1"

        # Act & Assert
        with pytest.raises(ValueError, match="Could not find lambda in response"):
            component._parse_lambda_from_response(response_text)

    def test_should_raise_error_when_lambda_format_is_invalid(self, component_class):
        # Arrange
        component = component_class()
        response_text = "lambda"

        # Act & Assert
        with pytest.raises(ValueError, match="Could not find lambda in response"):
            component._parse_lambda_from_response(response_text)

    def test_should_extract_lambda_with_complex_expression(self, component_class):
        # Arrange
        component = component_class()
        response_text = "lambda items: [item for item in items if item > 5]"

        # Act
        result = component._parse_lambda_from_response(response_text)

        # Assert
        assert callable(result)
        assert result([1, 6, 3, 8, 2]) == [6, 8]


class TestHandleProcessError(TestLambdaFilterComponent):
    """Tests for _handle_process_error method."""

    def test_should_raise_error_with_context_when_processing_fails(self, component_class):
        # Arrange
        component = component_class()
        component.data = Data(data={"key": "value"})
        original_error = Exception("Original error message")

        # Act & Assert
        with pytest.raises(ValueError, match="Failed to convert result to Data output"):
            component._handle_process_error(original_error, "Data")

    def test_should_include_input_type_in_error_message(self, component_class):
        # Arrange
        component = component_class()
        component.data = Message(text="test")
        original_error = Exception("Test error")

        # Act & Assert
        with pytest.raises(ValueError, match="Input type was Message"):
            component._handle_process_error(original_error, "DataFrame")

    def test_should_include_original_error_in_message(self, component_class):
        # Arrange
        component = component_class()
        component.data = []
        original_error = TypeError("Cannot convert type")

        # Act & Assert
        with pytest.raises(ValueError, match="Cannot convert type"):
            component._handle_process_error(original_error, "Message")


class TestConvertResultToData(TestLambdaFilterComponent):
    """Tests for _convert_result_to_data method."""

    def test_should_wrap_dict_when_result_is_dict(self, component_class):
        # Arrange
        component = component_class()
        result = {"key": "value"}

        # Act
        data = component._convert_result_to_data(result)

        # Assert
        assert isinstance(data, Data)
        assert data.data == {"key": "value"}

    def test_should_wrap_list_in_results_key_when_result_is_list(self, component_class):
        # Arrange
        component = component_class()
        result = [1, 2, 3]

        # Act
        data = component._convert_result_to_data(result)

        # Assert
        assert isinstance(data, Data)
        assert data.data == {"_results": [1, 2, 3]}

    def test_should_convert_to_string_when_result_is_other_type(self, component_class):
        # Arrange
        component = component_class()
        result = 42

        # Act
        data = component._convert_result_to_data(result)

        # Assert
        assert isinstance(data, Data)
        assert data.data == {"text": "42"}


class TestConvertResultToDataframe(TestLambdaFilterComponent):
    """Tests for _convert_result_to_dataframe method."""

    def test_should_create_dataframe_when_result_is_list_of_dicts(self, component_class):
        # Arrange
        component = component_class()
        result = [{"a": 1}, {"a": 2}]

        # Act
        df = component._convert_result_to_dataframe(result)

        # Assert
        assert isinstance(df, DataFrame)

    def test_should_wrap_values_when_result_is_list_of_non_dicts(self, component_class):
        # Arrange
        component = component_class()
        result = [1, 2, 3]

        # Act
        df = component._convert_result_to_dataframe(result)

        # Assert
        assert isinstance(df, DataFrame)

    def test_should_create_single_row_when_result_is_dict(self, component_class):
        # Arrange
        component = component_class()
        result = {"a": 1}

        # Act
        df = component._convert_result_to_dataframe(result)

        # Assert
        assert isinstance(df, DataFrame)


class TestConvertResultToMessage(TestLambdaFilterComponent):
    """Tests for _convert_result_to_message method."""

    def test_should_return_message_when_result_is_string(self, component_class):
        # Arrange
        component = component_class()
        result = "Hello World"

        # Act
        msg = component._convert_result_to_message(result)

        # Assert
        assert isinstance(msg, Message)
        assert msg.text == "Hello World"

    def test_should_join_items_when_result_is_list(self, component_class):
        # Arrange
        component = component_class()
        result = ["Line 1", "Line 2"]

        # Act
        msg = component._convert_result_to_message(result)

        # Assert
        assert isinstance(msg, Message)
        assert msg.text == "Line 1\nLine 2"

    def test_should_format_json_when_result_is_dict(self, component_class):
        # Arrange
        component = component_class()
        result = {"key": "value"}

        # Act
        msg = component._convert_result_to_message(result)

        # Assert
        assert isinstance(msg, Message)
        assert '"key": "value"' in msg.text


class TestProcessAsDataIntegration(TestLambdaFilterComponent):
    """Integration tests for process_as_data method."""

    @patch("lfx.base.models.unified_models.get_model_classes")
    async def test_should_return_filtered_data_when_lambda_is_valid(
        self, mock_get_model_classes, component_class, default_kwargs, mock_llm
    ):
        # Arrange
        mock_model_class = MagicMock(return_value=mock_llm)
        mock_get_model_classes.return_value = {"MockLanguageModel": mock_model_class}
        component = await self.component_setup(component_class, default_kwargs)
        mock_llm.ainvoke.return_value.content = "lambda x: [item for item in x['items'] if item['value'] > 15]"

        # Act
        result = await component.process_as_data()

        # Assert
        assert isinstance(result, Data)
        assert "_results" in result.data
        filtered_items = result.data["_results"]
        assert len(filtered_items) == 1
        assert filtered_items[0]["name"] == "test2"
        assert filtered_items[0]["value"] == 20

    @patch("lfx.base.models.unified_models.get_model_classes")
    async def test_should_raise_error_when_lambda_not_found_in_response(
        self, mock_get_model_classes, component_class, default_kwargs, mock_llm
    ):
        # Arrange
        mock_model_class = MagicMock(return_value=mock_llm)
        mock_get_model_classes.return_value = {"MockLanguageModel": mock_model_class}
        component = await self.component_setup(component_class, default_kwargs)
        mock_llm.ainvoke.return_value.content = "invalid response without lambda"

        # Act & Assert
        with pytest.raises(ValueError, match="Could not find lambda in response"):
            await component.process_as_data()


class TestProcessAsMessageIntegration(TestLambdaFilterComponent):
    """Integration tests for process_as_message with Message input."""

    @pytest.fixture
    def message_kwargs(self, model_metadata):
        """Return kwargs with Message input."""
        return {
            "data": [Message(text="Hello World")],
            "model": model_metadata,
            "api_key": "test-api-key",
            "filter_instruction": "Convert to uppercase",
            "sample_size": 1000,
            "max_size": 30000,
        }

    @patch("lfx.base.models.unified_models.get_model_classes")
    async def test_should_transform_message_when_input_is_message(
        self, mock_get_model_classes, component_class, message_kwargs, mock_llm
    ):
        # Arrange
        mock_model_class = MagicMock(return_value=mock_llm)
        mock_get_model_classes.return_value = {"MockLanguageModel": mock_model_class}
        component = await self.component_setup(component_class, message_kwargs)
        mock_llm.ainvoke.return_value.content = "lambda text: text.upper()"

        # Act
        result = await component.process_as_message()

        # Assert
        assert isinstance(result, Message)
        assert result.text == "HELLO WORLD"

    @patch("lfx.base.models.unified_models.get_model_classes")
    async def test_should_join_multiple_messages_when_input_is_list_of_messages(
        self, mock_get_model_classes, component_class, model_metadata, mock_llm
    ):
        # Arrange
        mock_model_class = MagicMock(return_value=mock_llm)
        mock_get_model_classes.return_value = {"MockLanguageModel": mock_model_class}
        kwargs = {
            "data": [Message(text="Hello"), Message(text="World")],
            "model": model_metadata,
            "api_key": "test-api-key",
            "filter_instruction": "Convert to uppercase",
            "sample_size": 1000,
            "max_size": 30000,
        }
        component = await self.component_setup(component_class, kwargs)
        mock_llm.ainvoke.return_value.content = "lambda text: text.upper()"

        # Act
        result = await component.process_as_message()

        # Assert
        assert isinstance(result, Message)
        assert result.text == "HELLO\n\nWORLD"


class TestProcessAsDataframeIntegration(TestLambdaFilterComponent):
    """Integration tests for process_as_dataframe method."""

    @patch("lfx.base.models.unified_models.get_model_classes")
    async def test_should_return_dataframe_when_lambda_returns_list_of_dicts(
        self, mock_get_model_classes, component_class, default_kwargs, mock_llm
    ):
        # Arrange
        mock_model_class = MagicMock(return_value=mock_llm)
        mock_get_model_classes.return_value = {"MockLanguageModel": mock_model_class}
        component = await self.component_setup(component_class, default_kwargs)
        mock_llm.ainvoke.return_value.content = "lambda x: x['items']"

        # Act
        result = await component.process_as_dataframe()

        # Assert
        assert isinstance(result, DataFrame)


class TestLargeDataset(TestLambdaFilterComponent):
    """Tests for handling large datasets."""

    @patch("lfx.base.models.unified_models.get_model_classes")
    async def test_should_filter_large_dataset_when_data_exceeds_max_size(
        self, mock_get_model_classes, component_class, default_kwargs, mock_llm
    ):
        # Arrange
        mock_model_class = MagicMock(return_value=mock_llm)
        mock_get_model_classes.return_value = {"MockLanguageModel": mock_model_class}
        large_data = {"items": [{"name": f"test{i}", "value": i} for i in range(2000)]}
        default_kwargs["data"] = [Data(data=large_data)]
        default_kwargs["filter_instruction"] = "Filter items with value greater than 1500"
        component = await self.component_setup(component_class, default_kwargs)
        mock_llm.ainvoke.return_value.content = "lambda x: [item for item in x['items'] if item['value'] > 1500]"

        # Act
        result = await component.process_as_data()

        # Assert
        assert isinstance(result, Data)
        filtered_items = result.data["_results"]
        assert len(filtered_items) == 499
        assert filtered_items[0]["value"] == 1501
        assert filtered_items[-1]["value"] == 1999


class TestComplexDataStructure(TestLambdaFilterComponent):
    """Tests for handling complex nested data structures."""

    @patch("lfx.base.models.unified_models.get_model_classes")
    async def test_should_handle_nested_data_when_structure_is_complex(
        self, mock_get_model_classes, component_class, default_kwargs, mock_llm
    ):
        # Arrange
        mock_model_class = MagicMock(return_value=mock_llm)
        mock_get_model_classes.return_value = {"MockLanguageModel": mock_model_class}
        complex_data = {
            "categories": {
                "A": [{"id": 1, "score": 90}, {"id": 2, "score": 85}],
                "B": [{"id": 3, "score": 95}, {"id": 4, "score": 88}],
            }
        }
        default_kwargs["data"] = [Data(data=complex_data)]
        default_kwargs["filter_instruction"] = "Filter items with score greater than 90"
        component = await self.component_setup(component_class, default_kwargs)
        mock_llm.ainvoke.return_value.content = (
            "lambda x: [item for cat in x['categories'].values() for item in cat if item['score'] > 90]"
        )

        # Act
        result = await component.process_as_data()

        # Assert
        assert isinstance(result, Data)
        filtered_items = result.data["_results"]
        assert len(filtered_items) == 1
        assert filtered_items[0]["id"] == 3
        assert filtered_items[0]["score"] == 95


class TestHttpApiDataTransformation(TestLambdaFilterComponent):
    """Tests for HTTP/API data transformation (PR #11128 scenario)."""

    @patch("lfx.base.models.unified_models.get_model_classes")
    async def test_should_handle_http_api_result_structure_when_filtering(
        self, mock_get_model_classes, component_class, model_metadata, mock_llm
    ):
        # Arrange
        mock_model_class = MagicMock(return_value=mock_llm)
        mock_get_model_classes.return_value = {"MockLanguageModel": mock_model_class}
        http_api_data = {
            "result": [
                {"id": 1, "status": "active"},
                {"id": 2, "status": "inactive"},
                {"id": 3, "status": "active"},
            ]
        }
        kwargs = {
            "data": [Data(data=http_api_data)],
            "model": model_metadata,
            "api_key": "test-api-key",
            "filter_instruction": "Filter items with active status",
            "sample_size": 1000,
            "max_size": 30000,
        }
        component = await self.component_setup(component_class, kwargs)
        # After normalization, data has '_results' key, so lambda uses '_results'
        mock_llm.ainvoke.return_value.content = (
            "lambda x: [item for item in x['_results'] if item['status'] == 'active']"
        )

        # Act
        result = await component.process_as_data()

        # Assert
        assert isinstance(result, Data)
        assert "_results" in result.data
        filtered_items = result.data["_results"]
        assert len(filtered_items) == 2
        assert all(item["status"] == "active" for item in filtered_items)

    @patch("lfx.base.models.unified_models.get_model_classes")
    async def test_should_work_when_llm_uses_results_key_after_normalization(
        self, mock_get_model_classes, component_class, model_metadata, mock_llm
    ):
        """
        Test that the data normalization ensures consistency between prompt and data.

        The prompt shows {"_results": [...]} to the LLM, so the LLM generates
        a lambda using '_results'. The actual data passed to the lambda is also
        normalized to have '_results' key, ensuring consistency.
        """
        # Arrange
        mock_model_class = MagicMock(return_value=mock_llm)
        mock_get_model_classes.return_value = {"MockLanguageModel": mock_model_class}
        http_api_data = {
            "result": [
                {"id": 1, "status": "active"},
                {"id": 2, "status": "inactive"},
            ]
        }
        kwargs = {
            "data": [Data(data=http_api_data)],
            "model": model_metadata,
            "api_key": "test-api-key",
            "filter_instruction": "Filter active items",
            "sample_size": 1000,
            "max_size": 30000,
        }
        component = await self.component_setup(component_class, kwargs)

        # LLM sees {"_results": [...]} in prompt, so it generates lambda with '_results'
        mock_llm.ainvoke.return_value.content = (
            "lambda x: [item for item in x['_results'] if item['status'] == 'active']"
        )

        # Act
        result = await component.process_as_data()

        # Assert - This should work if the data transformation is consistent
        assert isinstance(result, Data)
        assert "_results" in result.data
        filtered_items = result.data["_results"]
        assert len(filtered_items) == 1
        assert filtered_items[0]["id"] == 1

    def test_should_include_normalized_data_in_prompt_after_transformation(self, component_class):
        # Arrange
        component = component_class()
        component.max_size = 10000
        component.sample_size = 100
        component.filter_instruction = "Filter active items"
        http_api_data = {"result": [{"id": 1, "status": "active"}]}

        # First normalize the data (as _execute_lambda does)
        normalized_data = component._normalize_http_api_data(http_api_data)

        # Act - build prompt with normalized data
        prompt = component._build_data_prompt(normalized_data)

        # Assert
        assert '"_results"' in prompt
        assert '"id"' in prompt
        assert '"status"' in prompt


class TestEdgeCases(TestLambdaFilterComponent):
    """Tests for edge cases and boundary conditions."""

    def test_should_handle_empty_dict_in_extract_structured_data(self, component_class):
        # Arrange
        component = component_class()
        component.data = Data(data={})

        # Act
        result = component._extract_structured_data()

        # Assert
        assert result == {}

    def test_should_handle_data_with_nested_list_content(self, component_class):
        # Arrange
        component = component_class()
        component.data = Data(data={"items": [{"a": 1}, {"b": 2}]})

        # Act
        result = component._extract_structured_data()

        # Assert
        assert result == {"items": [{"a": 1}, {"b": 2}]}

    def test_should_return_unknown_when_input_type_is_unexpected(self, component_class):
        # Arrange
        component = component_class()
        component.data = "unexpected_string_type"

        # Act
        result = component._get_input_type_name()

        # Assert
        assert result == "unknown"

    def test_should_handle_mixed_list_in_extract_structured_data(self, component_class):
        # Arrange
        component = component_class()
        component.data = [
            Data(data={"a": 1}),
            DataFrame([{"b": 2}]),
        ]

        # Act
        result = component._extract_structured_data()

        # Assert
        assert isinstance(result, list)
        assert {"a": 1} in result
        assert {"b": 2} in result

    def test_should_handle_nested_empty_structures(self, component_class):
        # Arrange
        component = component_class()
        test_data = {"outer": {"inner": []}}

        # Act
        result = component.get_data_structure(test_data)

        # Assert
        assert result == {"outer": {"inner": []}}

    def test_should_normalize_result_with_empty_list(self, component_class):
        # Arrange
        component = component_class()
        data = {"result": []}

        # Act
        result = component._normalize_http_api_data(data)

        # Assert
        assert "_results" in result
        assert "result" not in result
        assert result["_results"] == []

import re

import pytest
from lfx.components.processing.batch_run import BatchRunComponent
from lfx.schema import DataFrame

from tests.base import ComponentTestBaseWithoutClient
from tests.unit.mock_language_model import MockLanguageModel


class TestBatchRunComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return BatchRunComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "model": MockLanguageModel(),
            "df": DataFrame({"text": ["Hello"]}),
            "column_name": "text",
            "enable_metadata": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    async def test_successful_batch_run_with_system_message(self):
        # Create test data
        test_df = DataFrame({"text": ["Hello", "World", "Test"]})

        component = BatchRunComponent(
            model=MockLanguageModel(),
            system_message="You are a helpful assistant",
            df=test_df,
            column_name="text",
            enable_metadata=True,
        )

        # Run the batch process
        result = await component.run_batch()

        # Verify the results
        assert isinstance(result, DataFrame)
        assert "text" in result.columns
        assert "model_response" in result.columns
        assert "metadata" in result.columns
        assert len(result) == 3
        assert all(isinstance(resp, str) for resp in result["model_response"])
        # Convert DataFrame to list of dicts for easier testing
        result_dicts = result.to_dict("records")
        # Verify metadata
        assert all(row["metadata"]["has_system_message"] for row in result_dicts)
        assert all(row["metadata"]["processing_status"] == "success" for row in result_dicts)

    async def test_batch_run_without_metadata(self):
        test_df = DataFrame({"text": ["Hello", "World"]})

        component = BatchRunComponent(
            model=MockLanguageModel(),
            df=test_df,
            column_name="text",
            enable_metadata=False,
        )

        result = await component.run_batch()

        assert isinstance(result, DataFrame)
        assert len(result) == 2
        assert "metadata" not in result.columns
        assert all(isinstance(resp, str) for resp in result["model_response"])

    async def test_batch_run_error_with_metadata(self):
        component = BatchRunComponent(
            model=MockLanguageModel(),
            df="not_a_dataframe",  # This will cause a TypeError
            column_name="text",
            enable_metadata=True,
        )

        with pytest.raises(TypeError, match=re.escape("Expected DataFrame input, got <class 'str'>")):
            await component.run_batch()

    async def test_batch_run_error_without_metadata(self):
        component = BatchRunComponent(
            model=MockLanguageModel(),
            df="not_a_dataframe",  # This will cause a TypeError
            column_name="text",
            enable_metadata=False,
        )

        with pytest.raises(TypeError, match=re.escape("Expected DataFrame input, got <class 'str'>")):
            await component.run_batch()

    async def test_operational_error_with_metadata(self):
        # Create a mock model that raises an AttributeError during processing
        class ErrorModel:
            def with_config(self, *_, **__):
                return self

            async def abatch(self, *_):
                msg = "Mock error during batch processing"
                raise AttributeError(msg)

        component = BatchRunComponent(
            model=ErrorModel(),
            df=DataFrame({"text": ["test1", "test2"]}),
            column_name="text",
            enable_metadata=True,
        )

        result = await component.run_batch()
        assert isinstance(result, DataFrame)
        assert len(result) == 1  # Component returns a single error row
        error_row = result.iloc[0]
        # Verify error metadata
        assert error_row["metadata"]["processing_status"] == "failed"
        assert "Mock error during batch processing" in error_row["metadata"]["error"]
        # Verify base row structure
        assert error_row["text"] == ""
        assert error_row["model_response"] == ""
        assert error_row["batch_index"] == -1

    async def test_operational_error_without_metadata(self):
        # Create a mock model that raises an AttributeError during processing
        class ErrorModel:
            def with_config(self, *_, **__):
                return self

            async def abatch(self, *_):
                msg = "Mock error during batch processing"
                raise AttributeError(msg)

        component = BatchRunComponent(
            model=ErrorModel(),
            df=DataFrame({"text": ["test1", "test2"]}),
            column_name="text",
            enable_metadata=False,
        )

        result = await component.run_batch()
        assert isinstance(result, DataFrame)
        assert len(result) == 1  # Component returns a single error row
        error_row = result.iloc[0]
        # Verify no metadata
        assert "metadata" not in error_row
        # Verify base row structure
        assert error_row["text"] == ""
        assert error_row["model_response"] == ""
        assert error_row["batch_index"] == -1

    def test_create_base_row(self):
        component = BatchRunComponent()
        row = component._create_base_row(
            original_row={"text_input": "test_input"},
            model_response="test_response",
            batch_index=1,
        )
        assert row["text_input"] == "test_input"
        assert row["model_response"] == "test_response"
        assert row["batch_index"] == 1

    def test_add_metadata_success(self):
        component = BatchRunComponent(enable_metadata=True)

        # Passa text_input dentro do dicionário original_row
        original_row = {"text_input": "test_input"}
        row = component._create_base_row(
            original_row=original_row,
            model_response="test_response",
            batch_index=1,
        )

        component._add_metadata(row, success=True, system_msg="Instructions here")

        assert "metadata" in row
        assert row["metadata"]["has_system_message"] is True
        assert row["metadata"]["input_length"] == len("test_input")
        assert row["metadata"]["response_length"] == len("test_response")
        assert row["metadata"]["processing_status"] == "success"

    def test_add_metadata_failure(self):
        component = BatchRunComponent(enable_metadata=True)

        # Fornecendo um original_row vazio (poderia conter outras chaves se necessário)
        row = component._create_base_row(original_row={}, model_response="", batch_index=1)

        # Adiciona metadata simulando falha
        component._add_metadata(row, success=False, error="Simulated error")

        assert "metadata" in row
        assert row["metadata"]["processing_status"] == "failed"
        assert row["metadata"]["error"] == "Simulated error"

    def test_metadata_disabled(self):
        component = BatchRunComponent(enable_metadata=False)

        # Fornece text_input dentro do dicionário original_row
        row = component._create_base_row(
            original_row={"text_input": "test"},
            model_response="response",
            batch_index=0,
        )

        component._add_metadata(row, success=True, system_msg="test")

        # Como o metadata está desabilitado, ele não deve existir
        assert "metadata" not in row

    async def test_invalid_column_name(self):
        component = BatchRunComponent(
            model=MockLanguageModel(),
            df=DataFrame({"text": ["Hello"]}),
            column_name="nonexistent_column",
            enable_metadata=True,
        )

        with pytest.raises(
            ValueError,
            match=re.escape("Column 'nonexistent_column' not found in the DataFrame. Available columns: text"),
        ):
            await component.run_batch()

    async def test_empty_dataframe(self):
        component = BatchRunComponent(
            model=MockLanguageModel(),
            df=DataFrame({"text": []}),
            column_name="text",
            enable_metadata=True,
        )

        result = await component.run_batch()
        assert isinstance(result, DataFrame)
        assert len(result) == 0

    async def test_non_string_column_conversion(self):
        test_df = DataFrame({"text": [123, 456, 789]})  # Numeric values

        component = BatchRunComponent(
            model=MockLanguageModel(),
            df=test_df,
            column_name="text",
            enable_metadata=True,
        )

        result = await component.run_batch()

        assert isinstance(result, DataFrame)
        assert all(isinstance(text, int) for text in result["text"])
        assert all(
            str(num) in response for num, response in zip(test_df["text"], result["model_response"], strict=False)
        )
        result_dicts = result.to_dict("records")
        assert all(row["metadata"]["processing_status"] == "success" for row in result_dicts)

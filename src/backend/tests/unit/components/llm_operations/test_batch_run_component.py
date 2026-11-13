import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, call, patch

import pytest
from langchain_core.messages import AIMessage
from lfx.components.llm_operations.batch_run import BatchRunComponent
from lfx.schema import DataFrame

from tests.base import ComponentTestBaseWithoutClient


class _BatchModel:
    """Small async model double that records the size of each submitted batch."""

    def __init__(self, handler):
        """Store the batch response handler and initialize call tracking."""
        self.handler = handler
        self.batch_sizes = []

    async def abatch(self, conversations, **_kwargs):
        """Return handler responses for one batch and record its size."""
        self.batch_sizes.append(len(conversations))
        return self.handler(conversations)


def _conversations(count):
    """Build simple user-only conversations for the requested number of rows."""
    return [[{"role": "user", "content": str(index)}] for index in range(count)]


@pytest.mark.asyncio
async def test_run_conversations_limits_batch_size_and_delays_between_batches():
    """Submit no more than the configured batch size and pause between batches."""
    model = _BatchModel(lambda batch: [item[0]["content"] for item in batch])
    component = BatchRunComponent(batch_size=2, delay_between_batches=0.25)

    with patch("lfx.components.llm_operations.batch_run.asyncio.sleep", new_callable=AsyncMock) as sleep:
        results = await component._run_conversations(model, _conversations(5))

    assert results == ["0", "1", "2", "3", "4"]
    assert model.batch_sizes == [2, 2, 1]
    assert sleep.await_args_list == [call(0.25), call(0.25)]


@pytest.mark.asyncio
async def test_run_conversations_reduces_batch_and_retries_rate_limited_rows():
    """Retry 429 responses with a smaller batch and provider-specified delay."""

    class RateLimitError(Exception):
        status_code = 429
        response = SimpleNamespace(headers={"Retry-After": "7.5"})

    def handle_batch(batch):
        """Return rate-limit errors once, then successful responses."""
        if not model.batch_sizes[:-1]:
            return [RateLimitError("busy") for _ in batch]
        return [f"ok:{item[0]['content']}" for item in batch]

    model = _BatchModel(handle_batch)
    component = BatchRunComponent(batch_size=4, max_rate_limit_retries=1)

    with patch("lfx.components.llm_operations.batch_run.asyncio.sleep", new_callable=AsyncMock) as sleep:
        results = await component._run_conversations(model, _conversations(4))

    assert results == ["ok:0", "ok:1", "ok:2", "ok:3"]
    assert model.batch_sizes == [4, 2, 2]
    sleep.assert_awaited_once_with(7.5)


def test_rate_limit_detection_and_retry_after_bounds():
    """Recognize common rate-limit signals and bound numeric retry delays."""
    component = BatchRunComponent()

    assert component._is_rate_limit_error(SimpleNamespace(status_code=429))
    assert not component._is_rate_limit_error(SimpleNamespace(status_code=503, message="rate limit"))
    assert component._is_rate_limit_error(RuntimeError("rate limit exceeded"))
    assert component._retry_after_seconds(SimpleNamespace(retry_after="12")) == 12
    assert component._retry_after_seconds(SimpleNamespace(retry_after="nan")) is None
    assert component._retry_after_seconds(SimpleNamespace(retry_after="inf")) is None
    assert component._retry_after_seconds(SimpleNamespace(retry_after="9999")) == 300


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("wrap_error", "retry_after"),
    [(False, None), (True, None), (True, "7.5")],
)
async def test_run_conversations_retries_provider_quota_errors(wrap_error, retry_after):
    """Recover from provider codes and wrapped quota errors without retrying successful rows."""

    class ProviderQuotaError(Exception):
        code = 429
        response = SimpleNamespace(headers={"Retry-After": retry_after})

    error = ProviderQuotaError("RESOURCE_EXHAUSTED")
    if wrap_error:
        wrapped_error = RuntimeError("Error calling model (RESOURCE_EXHAUSTED)")
        wrapped_error.__cause__ = error
        wrapped_error.retry_after = "invalid"
        error = wrapped_error

    def handle_batch(batch):
        """Return a quota error once, followed by successful retry responses."""
        if len(model.batch_sizes) == 1:
            return [error, "ok:1"]
        return [f"ok:{item[0]['content']}" for item in batch]

    model = _BatchModel(handle_batch)
    component = BatchRunComponent(batch_size=2, max_rate_limit_retries=1)

    with patch("lfx.components.llm_operations.batch_run.asyncio.sleep", new_callable=AsyncMock) as sleep:
        results = await component._run_conversations(model, _conversations(2))

    assert results == ["ok:0", "ok:1"]
    assert model.batch_sizes == [2, 1]
    sleep.assert_awaited_once_with(float(retry_after) if retry_after is not None else 1)


@pytest.mark.asyncio
async def test_run_conversations_does_not_retry_wrapped_non_rate_limit_errors():
    """Use the provider's concrete status instead of misleading wrapper text."""

    class ProviderError(Exception):
        code = 503

    error = RuntimeError("rate limit request failed")
    error.__cause__ = ProviderError("Service unavailable")
    model = _BatchModel(lambda batch: [error for _ in batch])
    component = BatchRunComponent(max_rate_limit_retries=3)

    with (
        patch("lfx.components.llm_operations.batch_run.asyncio.sleep", new_callable=AsyncMock) as sleep,
        pytest.raises(RuntimeError) as raised,
    ):
        await component._run_conversations(model, _conversations(1))

    assert raised.value is error
    assert model.batch_sizes == [1]
    sleep.assert_not_awaited()


def test_rate_limit_helpers_stop_at_cyclic_causes():
    """Terminate when a provider constructs a cyclic exception cause chain."""
    error = RuntimeError("Provider failed")
    cause = RuntimeError("Request failed")
    error.__cause__ = cause
    cause.__cause__ = error
    component = BatchRunComponent()

    assert not component._is_rate_limit_error(error)
    assert component._retry_after_seconds(error) is None


@pytest.mark.asyncio
async def test_run_conversations_stops_after_retry_limit():
    """Raise the provider error without sleeping when retries are disabled."""

    class RateLimitError(Exception):
        status_code = 429

    model = _BatchModel(lambda batch: [RateLimitError("busy") for _ in batch])
    component = BatchRunComponent(batch_size=2, max_rate_limit_retries=0)

    with (
        patch("lfx.components.llm_operations.batch_run.asyncio.sleep", new_callable=AsyncMock) as sleep,
        pytest.raises(RateLimitError),
    ):
        await component._run_conversations(model, _conversations(2))

    assert model.batch_sizes == [2]
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_conversations_uses_exponential_backoff_without_retry_after():
    """Apply increasing fallback delays when a provider omits Retry-After."""

    class RateLimitError(Exception):
        status_code = 429

    attempts = 0

    def handle_batch(batch):
        """Rate-limit the first two attempts before returning successful responses."""
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return [RateLimitError("busy") for _ in batch]
        return [f"ok:{item[0]['content']}" for item in batch]

    model = _BatchModel(handle_batch)
    component = BatchRunComponent(batch_size=4, max_rate_limit_retries=2)

    with patch("lfx.components.llm_operations.batch_run.asyncio.sleep", new_callable=AsyncMock) as sleep:
        results = await component._run_conversations(model, _conversations(1))

    assert results == ["ok:0"]
    assert model.batch_sizes == [1, 1, 1]
    assert sleep.await_args_list == [call(1), call(2)]


@pytest.mark.asyncio
async def test_run_batch_retries_only_rate_limited_rows_and_preserves_order():
    """Keep successful rows and return retried rows in their original order."""

    class RateLimitError(Exception):
        status_code = 429

    class MixedResultModel:
        def __init__(self):
            """Track calls so the first response can mix successes and 429s."""
            self.calls = 0
            self.submitted_ids = []

        def with_config(self, *_, **__):
            """Return this model unchanged, as a configured runnable would."""
            return self

        async def abatch(self, conversations, **_kwargs):
            """Mix successful messages with rate limits, then answer retries."""
            self.calls += 1
            submitted_ids = [conversation[-1]["content"] for conversation in conversations]
            self.submitted_ids.append(submitted_ids)
            if self.calls == 1:
                return [
                    AIMessage(content="response-0"),
                    RateLimitError("busy-1"),
                    AIMessage(content="response-2"),
                    RateLimitError("busy-3"),
                ]
            return [AIMessage(content=f"response-{conversation[-1]['content']}") for conversation in conversations]

    model = MixedResultModel()
    component = BatchRunComponent(
        model=model,
        df=DataFrame({"text": ["0", "1", "2", "3"]}),
        column_name="text",
        batch_size=4,
        max_rate_limit_retries=1,
    )

    with patch("lfx.components.llm_operations.batch_run.asyncio.sleep", new_callable=AsyncMock) as sleep:
        result = await component.run_batch()

    assert result["model_response"].tolist() == ["response-0", "response-1", "response-2", "response-3"]
    assert result["batch_index"].tolist() == [0, 1, 2, 3]
    assert model.calls == 2
    assert model.submitted_ids == [["0", "1", "2", "3"], ["1", "3"]]
    sleep.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_custom_abatch_fallback_retries_direct_rate_limit_errors():
    """Retry whole-batch 429s from custom models without return_exceptions."""

    class RateLimitError(Exception):
        status_code = 429

    class CustomModel:
        def __init__(self):
            """Track submitted rows and fail the first call with a direct 429."""
            self.calls = []

        async def abatch(self, conversations):
            """Expose the legacy signature and raise a batch-level rate limit."""
            ids = [conversation[-1]["content"] for conversation in conversations]
            self.calls.append(ids)
            if len(self.calls) == 1:
                error_message = "busy"
                raise RateLimitError(error_message)
            return [f"ok:{row_id}" for row_id in ids]

    model = CustomModel()
    component = BatchRunComponent(batch_size=2, max_rate_limit_retries=1)

    with patch("lfx.components.llm_operations.batch_run.asyncio.sleep", new_callable=AsyncMock) as sleep:
        results = await component._run_conversations(model, _conversations(2))

    assert results == ["ok:0", "ok:1"]
    assert model.calls == [["0", "1"], ["0"], ["1"]]
    sleep.assert_awaited_once_with(1)


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [429, 503])
async def test_custom_abatch_handles_direct_errors_with_return_exceptions(status_code):
    """Retry direct 429s from the modern signature while propagating other failures."""

    class ProviderError(Exception):
        pass

    error = ProviderError("Provider failed")
    error.status_code = status_code

    class CustomModel:
        def __init__(self):
            """Track inputs to verify that a direct error enters the retry path."""
            self.calls = []

        async def abatch(self, conversations, *, return_exceptions=False):
            """Accept the modern argument but report the first failure directly."""
            assert return_exceptions
            ids = [conversation[-1]["content"] for conversation in conversations]
            self.calls.append(ids)
            if len(self.calls) == 1:
                raise error
            return [f"ok:{row_id}" for row_id in ids]

    model = CustomModel()
    component = BatchRunComponent(batch_size=2, max_rate_limit_retries=1)

    with patch("lfx.components.llm_operations.batch_run.asyncio.sleep", new_callable=AsyncMock) as sleep:
        if status_code == 429:
            results = await component._run_conversations(model, _conversations(2))
            assert results == ["ok:0", "ok:1"]
            assert model.calls == [["0", "1"], ["0"], ["1"]]
            sleep.assert_awaited_once_with(1)
        else:
            with pytest.raises(ProviderError) as raised:
                await component._run_conversations(model, _conversations(2))
            assert raised.value is error
            assert model.calls == [["0", "1"]]
            sleep.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("retry_after", "configured_delay", "expected_delay"),
    [("0", 0.0, 0.0), ("0.5", 0.0, 0.5), ("0.5", 1.25, 1.25)],
)
async def test_run_conversations_honors_short_retry_after(retry_after, configured_delay, expected_delay):
    """Use present provider delays while preserving the configured minimum wait."""

    class RateLimitError(Exception):
        status_code = 429
        response = SimpleNamespace(headers={"Retry-After": retry_after})

    def handle_batch(batch):
        """Limit the first request, then return a successful response."""
        if len(model.batch_sizes) == 1:
            return [RateLimitError("busy")]
        return [item[0]["content"] for item in batch]

    model = _BatchModel(handle_batch)
    component = BatchRunComponent(delay_between_batches=configured_delay, max_rate_limit_retries=1)

    with patch("lfx.components.llm_operations.batch_run.asyncio.sleep", new_callable=AsyncMock) as sleep:
        results = await component._run_conversations(model, _conversations(1))

    assert results == ["0"]
    assert model.batch_sizes == [1, 1]
    sleep.assert_awaited_once_with(expected_delay)


@pytest.mark.asyncio
async def test_run_conversations_backs_off_headerless_rows_in_mixed_batch():
    """A short provider delay must not suppress another row's fallback wait."""

    class RateLimitError(Exception):
        status_code = 429

    immediate_error = RateLimitError("busy")
    immediate_error.retry_after = 0
    headerless_error = RateLimitError("busy")

    def handle_batch(batch):
        """Limit two rows with different delay guidance, then answer retries."""
        if len(model.batch_sizes) == 1:
            return [immediate_error, headerless_error]
        return [f"ok:{item[0]['content']}" for item in batch]

    model = _BatchModel(handle_batch)
    component = BatchRunComponent(batch_size=2, max_rate_limit_retries=1)

    with patch("lfx.components.llm_operations.batch_run.asyncio.sleep", new_callable=AsyncMock) as sleep:
        results = await component._run_conversations(model, _conversations(2))

    assert results == ["ok:0", "ok:1"]
    assert model.batch_sizes == [2, 1, 1]
    sleep.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_run_conversations_propagates_non_rate_limit_errors_immediately():
    """Propagate ordinary model failures instead of retrying them."""
    error = ValueError("invalid request")
    model = _BatchModel(lambda batch: [error for _ in batch])
    component = BatchRunComponent(batch_size=2, max_rate_limit_retries=3)

    with (
        patch("lfx.components.llm_operations.batch_run.asyncio.sleep", new_callable=AsyncMock) as sleep,
        pytest.raises(ValueError, match="invalid request") as raised,
    ):
        await component._run_conversations(model, _conversations(2))

    assert raised.value is error
    assert model.batch_sizes == [2]
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_conversations_rejects_response_count_mismatch():
    """Reject providers that return fewer responses than submitted requests."""
    model = _BatchModel(lambda _batch: ["only one response"])
    component = BatchRunComponent(batch_size=2)

    with pytest.raises(ValueError, match="different number of responses"):
        await component._run_conversations(model, _conversations(2))


class _MockLLM:
    """Minimal mock LLM for unit-testing batch processing without live API keys."""

    def with_config(self, *_, **__):
        return self

    async def abatch(self, conversations):
        return [AIMessage(content=f"Response to: {conv[-1]['content']}") for conv in conversations]


class TestBatchRunComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return BatchRunComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            # A connected model, so the batch runs offline instead of calling a provider.
            "model": _MockLLM(),
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
            model=_MockLLM(),
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

    async def test_metadata_reports_input_length(self):
        test_df = DataFrame({"text": ["Hi", "Hello there"]})

        component = BatchRunComponent(
            model=_MockLLM(),
            df=test_df,
            column_name="text",
            enable_metadata=True,
        )

        result = await component.run_batch()

        assert [row["metadata"]["input_length"] for row in result.to_dict("records")] == [2, 11]

    async def test_metadata_reports_column_input_format(self):
        component = BatchRunComponent(
            model=_MockLLM(),
            df=DataFrame({"text": ["Hi", "Hello there"]}),
            column_name="text",
            enable_metadata=True,
        )

        result = await component.run_batch()

        assert [row["metadata"]["input_format"] for row in result.to_dict("records")] == ["column", "column"]

    async def test_metadata_reports_toml_length_and_format_when_column_name_empty(self):
        component = BatchRunComponent(
            model=_MockLLM(),
            df=DataFrame({"name": ["Ada"], "city": ["Lagos"]}),
            column_name="",
            enable_metadata=True,
        )

        result = await component.run_batch()

        metadata = result.to_dict("records")[0]["metadata"]
        sent_text = '[name]\nvalue = "Ada"\n\n[city]\nvalue = "Lagos"\n'
        assert result.to_dict("records")[0]["model_response"] == f"Response to: {sent_text}"
        assert metadata["input_length"] == len(sent_text) == 45
        assert metadata["input_format"] == "toml"

    async def test_metadata_ignores_text_input_column(self):
        component = BatchRunComponent(
            model=_MockLLM(),
            df=DataFrame({"text": ["Hi"], "text_input": ["xxxxxxxxxx"]}),
            column_name="text",
            enable_metadata=True,
        )

        result = await component.run_batch()

        metadata = result.to_dict("records")[0]["metadata"]
        assert metadata["input_length"] == 2
        assert metadata["input_format"] == "column"

    def test_failure_metadata_omits_input_fields(self):
        component = BatchRunComponent(enable_metadata=True)
        row = component._create_base_row(original_row={}, model_response="", batch_index=-1)

        component._add_metadata(row, success=False, input_text="abc", input_format="column", error="boom")

        assert row["metadata"] == {"error": "boom", "processing_status": "failed"}

    def test_metadata_disabled_ignores_input_fields(self):
        component = BatchRunComponent(enable_metadata=False)
        row = component._create_base_row(original_row={"text": "x"}, model_response="r", batch_index=0)

        component._add_metadata(row, success=True, input_text="x", input_format="toml")

        assert "metadata" not in row

    async def test_failed_batch_metadata_has_only_error_and_status(self):
        class _FailingLLM(_MockLLM):
            async def abatch(self, *_):
                msg = "boom"
                raise KeyError(msg)

        component = BatchRunComponent(
            model=_FailingLLM(),
            df=DataFrame({"text": ["Hi"]}),
            column_name="text",
            enable_metadata=True,
        )

        result = await component.run_batch()

        rows = result.to_dict("records")
        assert len(rows) == 1
        assert rows[0]["batch_index"] == -1
        assert rows[0]["metadata"] == {"error": "'boom'", "processing_status": "failed"}

    async def test_metadata_input_length_excludes_system_message(self):
        component = BatchRunComponent(
            model=_MockLLM(),
            df=DataFrame({"text": ["Hi"]}),
            column_name="text",
            system_message="Answer in one word.",
            enable_metadata=True,
        )

        result = await component.run_batch()

        metadata = result.to_dict("records")[0]["metadata"]
        assert metadata["has_system_message"] is True
        assert metadata["input_length"] == 2

    async def test_metadata_counts_stringified_non_string_cells(self):
        component = BatchRunComponent(
            model=_MockLLM(),
            df=DataFrame({"number": [7, 12345]}),
            column_name="number",
            enable_metadata=True,
        )

        result = await component.run_batch()

        assert [row["metadata"]["input_length"] for row in result.to_dict("records")] == [1, 5]

    async def test_metadata_counts_none_cell_as_sent_in_toml(self):
        component = BatchRunComponent(
            model=_MockLLM(),
            df=DataFrame({"name": ["Ada"], "city": [None]}),
            column_name="",
            enable_metadata=True,
        )

        result = await component.run_batch()

        row = result.to_dict("records")[0]
        sent_text = '[name]\nvalue = "Ada"\n\n[city]\nvalue = "None"\n'
        assert row["model_response"] == f"Response to: {sent_text}"
        assert row["metadata"]["input_length"] == len(sent_text) == 44
        assert row["metadata"]["input_format"] == "toml"

    async def test_batch_run_without_metadata(self):
        test_df = DataFrame({"text": ["Hello", "World"]})

        component = BatchRunComponent(
            model=_MockLLM(),
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
            model=_MockLLM(),
            df="not_a_dataframe",  # This will cause a TypeError
            column_name="text",
            enable_metadata=True,
        )

        with pytest.raises(TypeError, match=re.escape("Expected DataFrame input, got <class 'str'>")):
            await component.run_batch()

    async def test_batch_run_error_without_metadata(self):
        component = BatchRunComponent(
            model=_MockLLM(),
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

        original_row = {"text": "test_input"}
        row = component._create_base_row(
            original_row=original_row,
            model_response="test_response",
            batch_index=1,
        )

        component._add_metadata(row, success=True, system_msg="Instructions here", input_text="test_input")

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
            model=_MockLLM(),
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
            model=_MockLLM(),
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
            model=_MockLLM(),
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

    async def test_with_config_failure_handling(self):
        """Test that batch run handles models that fail with_config() gracefully."""

        # Create a mock model that raises an error during with_config()
        class ConfigFailureModel:
            def with_config(self, *_, **__):
                msg = "Serialization error: SecretStr cannot be serialized"
                raise ValueError(msg)

            async def abatch(self, conversations):
                # Model should still work without config
                return [AIMessage(content=f"Response to: {conv[0]['content']}") for conv in conversations]

        test_df = DataFrame({"text": ["test1", "test2"]})
        component = BatchRunComponent(
            model=ConfigFailureModel(),
            df=test_df,
            column_name="text",
            enable_metadata=False,
        )

        # Should complete successfully despite with_config() failure
        result = await component.run_batch()

        assert isinstance(result, DataFrame)
        assert len(result) == 2
        assert "model_response" in result.columns
        assert all(isinstance(resp, str) for resp in result["model_response"])

    # ---------------------------------------------------------------------------
    # update_build_config field-visibility tests (#2)
    # ---------------------------------------------------------------------------

    def _get_build_config(self, component):
        """Helper to get a fresh build_config dict from the component's frontend node."""
        return component.to_frontend_node()["data"]["node"]["template"]

    @patch("lfx.base.models.unified_models.get_language_model_options")
    async def test_update_build_config_shows_watsonx_fields_when_watsonx_selected(
        self, mock_opts, component_class, default_kwargs
    ):
        """Selecting IBM WatsonX should show base_url_ibm_watsonx and project_id fields."""
        watsonx_model = [{"name": "ibm/granite-13b-chat-v2", "provider": "IBM WatsonX", "metadata": {}}]
        mock_opts.return_value = watsonx_model
        component = component_class(**default_kwargs)
        component._user_id = None

        build_config = self._get_build_config(component)

        updated = component.update_build_config(build_config, watsonx_model, field_name="model")

        assert updated["base_url_ibm_watsonx"]["show"] is True
        assert updated["base_url_ibm_watsonx"]["required"] is False
        assert updated["project_id"]["show"] is True

    @patch("lfx.base.models.unified_models.get_language_model_options")
    async def test_update_build_config_hides_watsonx_fields_when_openai_selected(
        self, mock_opts, component_class, default_kwargs
    ):
        """Selecting OpenAI should hide WatsonX-specific fields."""
        openai_model = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]
        mock_opts.return_value = openai_model
        component = component_class(**default_kwargs)
        component._user_id = None

        build_config = self._get_build_config(component)

        updated = component.update_build_config(build_config, openai_model, field_name="model")

        assert updated["base_url_ibm_watsonx"]["show"] is False
        assert updated["project_id"]["show"] is False

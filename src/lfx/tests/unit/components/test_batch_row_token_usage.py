"""Sum independent final row responses without changing chunk accumulation semantics."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk
from lfx.components.llm_operations.batch_run import BatchRunComponent
from lfx.schema.dataframe import DataFrame
from lfx.schema.properties import Usage
from lfx.schema.token_usage import accumulate_usage


def response(text, inputs=3, outputs=4, *, chunk=False):
    cls = AIMessageChunk if chunk else AIMessage
    return cls(
        content=text,
        usage_metadata={"input_tokens": inputs, "output_tokens": outputs, "total_tokens": inputs + outputs},
    )


def make(monkeypatch, responses, rows=2):
    model = SimpleNamespace(abatch=AsyncMock(return_value=responses), with_config=Mock())
    model.with_config.return_value = model
    c = BatchRunComponent(model=model)
    c.set_attributes(
        {
            "df": DataFrame([{"text": str(i)} for i in range(rows)]),
            "column_name": "text" if rows else "",
            "system_message": "",
            "output_column_name": "model_response",
            "enable_metadata": True,
        }
    )
    monkeypatch.setattr(c, "get_project_name", Mock(return_value=None))
    monkeypatch.setattr(c, "get_langchain_callbacks", Mock(return_value=[]))
    return c, model


@pytest.mark.asyncio
@pytest.mark.parametrize("chunk", [False, True])
async def test_independent_rows_sum_final_usage_and_keep_order(monkeypatch, chunk):
    c, model = make(monkeypatch, [response("first", 3, 4, chunk=chunk), response("second", 5, 6, chunk=chunk)])
    result = await c.run_batch()
    assert result["model_response"].tolist() == ["first", "second"]
    assert result["batch_index"].tolist() == [0, 1]
    assert c._token_usage == Usage(input_tokens=8, output_tokens=10, total_tokens=18)
    model.abatch.assert_awaited_once()


@pytest.mark.asyncio
async def test_empty_batch_clears_previous_usage(monkeypatch):
    c, _model = make(monkeypatch, [], rows=0)
    c._token_usage = Usage(input_tokens=99, output_tokens=99, total_tokens=198)
    result = await c.run_batch()
    assert result.empty
    assert c._token_usage is None


@pytest.mark.asyncio
async def test_repeated_component_invocations_do_not_carry_previous_totals(monkeypatch):
    c, model = make(monkeypatch, [response("first"), response("second")])
    await c.run_batch()
    assert c._token_usage.total_tokens == 14
    model.abatch.return_value = [response("first", 1, 1), response("second", 2, 2)]
    await c.run_batch()
    assert c._token_usage == Usage(input_tokens=3, output_tokens=3, total_tokens=6)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("responses", "expected"),
    [
        ([AIMessage(content="first"), AIMessage(content="second")], None),
        ([AIMessage(content="first"), response("second")], Usage(input_tokens=3, output_tokens=4, total_tokens=7)),
        (
            [
                AIMessage(content="first", response_metadata={"token_usage": {"total_tokens": 9}}),
                AIMessage(content="second", response_metadata={"token_usage": {"total_tokens": 4}}),
            ],
            Usage(input_tokens=None, output_tokens=None, total_tokens=13),
        ),
        (
            [
                AIMessage(
                    content="first", response_metadata={"token_usage": {"prompt_tokens": 3, "completion_tokens": 4}}
                ),
                AIMessage(
                    content="second", response_metadata={"token_usage": {"prompt_tokens": 5, "completion_tokens": 6}}
                ),
            ],
            Usage(input_tokens=8, output_tokens=10, total_tokens=18),
        ),
        ([AIMessage(content="first", response_metadata={"token_usage": {}}), AIMessage(content="second")], None),
        (
            [
                AIMessage(
                    content="first",
                    response_metadata={"token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}},
                ),
                AIMessage(content="second"),
            ],
            Usage(input_tokens=0, output_tokens=0, total_tokens=0),
        ),
    ],
)
async def test_unknown_partial_and_total_only_usage_is_not_invented(monkeypatch, responses, expected):
    c, _model = make(monkeypatch, responses)
    await c.run_batch()
    assert c._token_usage == expected


@pytest.mark.asyncio
async def test_provider_failure_preserves_exception_and_discards_stale_usage(monkeypatch):
    c, model = make(monkeypatch, [])
    c._token_usage = Usage(input_tokens=99, output_tokens=99, total_tokens=198)
    failure = RuntimeError("provider failed")
    model.abatch.side_effect = failure
    with pytest.raises(RuntimeError) as caught:
        await c.run_batch()
    assert caught.value is failure
    assert c._token_usage is None


@pytest.mark.asyncio
async def test_cancelled_provider_releases_work_and_never_reuses_old_usage(monkeypatch):
    c, model = make(monkeypatch, [])
    c._token_usage = Usage(input_tokens=99, output_tokens=99, total_tokens=198)
    entered = asyncio.Event()
    closed = []

    async def wait(_conversations):
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            closed.append(True)

    model.abatch.side_effect = wait
    task = asyncio.create_task(c.run_batch())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed == [True]
    assert c._token_usage is None


@pytest.mark.asyncio
async def test_response_count_error_keeps_available_completed_usage(monkeypatch):
    c, _model = make(monkeypatch, [response("only-response")])
    with pytest.raises(ValueError, match=r"zip.*(shorter|longer)"):
        await c.run_batch()
    assert c._token_usage == Usage(input_tokens=3, output_tokens=4, total_tokens=7)


def test_shared_cumulative_chunk_merging_is_unchanged():
    assert accumulate_usage(
        Usage(input_tokens=3, output_tokens=4, total_tokens=7), Usage(input_tokens=3, output_tokens=6, total_tokens=9)
    ) == Usage(input_tokens=3, output_tokens=6, total_tokens=9)


@pytest.mark.asyncio
async def test_row_format_error_retains_completed_response_usage(monkeypatch):
    class BrokenResponse:
        usage_metadata = {"input_tokens": 5, "output_tokens": 6, "total_tokens": 11}
        response_metadata = {}

        @property
        def content(self):
            msg = "row content unavailable"
            raise KeyError(msg)

    c, _model = make(monkeypatch, [response("first"), BrokenResponse()])
    result = await c.run_batch()
    assert result["batch_index"].tolist() == [-1]
    assert result.iloc[0]["metadata"]["processing_status"] == "failed"
    assert c._token_usage == Usage(input_tokens=8, output_tokens=10, total_tokens=18)


@pytest.mark.asyncio
async def test_custom_iterable_response_sequence_is_consumed_once(monkeypatch):
    rows = [response("first"), response("second", 5, 6)]
    c, _model = make(monkeypatch, iter(rows))
    result = await c.run_batch()
    assert result["model_response"].tolist() == ["first", "second"]
    assert c._token_usage.total_tokens == 18


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_reset_before_native_factory_failure_or_cancel(monkeypatch, cancel):
    from lfx.components.llm_operations import batch_run

    c = BatchRunComponent(model=[{"name": "test-model", "provider": "OpenAI", "metadata": {}}])
    c.set(df=DataFrame([{"text": "one"}]), column_name="text", system_message="", enable_metadata=False)
    c._token_usage = Usage(input_tokens=99, output_tokens=99, total_tokens=198)
    entered = asyncio.Event()
    released = []

    async def factory(**_kwargs):
        try:
            entered.set()
            if cancel:
                await asyncio.Event().wait()
            msg = "lookup failed"
            raise RuntimeError(msg)
        finally:
            released.append(True)

    monkeypatch.setattr(batch_run, "aget_llm", factory)
    task = asyncio.create_task(c.run_batch())
    await entered.wait()
    if cancel:
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
        await task
    assert c._token_usage is None
    assert released == [True]


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["frame", "column"])
async def test_reset_before_invalid_input_error(monkeypatch, invalid):
    c, model = make(monkeypatch, [response("unused")])
    c._token_usage = Usage(input_tokens=99, output_tokens=99, total_tokens=198)
    if invalid == "frame":
        c.df = None
    else:
        c.column_name = "missing-column"
    with pytest.raises(TypeError if invalid == "frame" else ValueError):
        await c.run_batch()
    assert c._token_usage is None
    model.abatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_extra_response_count_error_retains_available_usage(monkeypatch):
    c, _model = make(monkeypatch, [response("one"), response("two"), response("extra")])
    with pytest.raises(ValueError, match=r"zip.*(shorter|longer)"):
        await c.run_batch()
    assert c._token_usage == Usage(input_tokens=9, output_tokens=12, total_tokens=21)

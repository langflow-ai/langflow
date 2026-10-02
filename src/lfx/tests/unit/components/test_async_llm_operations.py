"""Async row/transform operations await scoped model construction before invocation."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

SELECTION = [{"name": "test-model", "provider": "OpenAI", "metadata": {}}]


@pytest.fixture(params=["batch", "lambda"])
def operation(request, monkeypatch):
    from lfx.schema.dataframe import DataFrame
    from lfx.schema.message import Message

    if request.param == "batch":
        from lfx.components.llm_operations import batch_run as module

        c = module.BatchRunComponent(_user_id="runtime-owner", model=SELECTION, api_key="test-key")
        c.set_attributes(
            {
                "df": DataFrame([{"text": "one"}, {"text": "two"}]),
                "column_name": "text",
                "system_message": "instructions",
                "output_column_name": "model_response",
                "enable_metadata": False,
            }
        )
        monkeypatch.setattr(c, "get_project_name", Mock(return_value=None))
        monkeypatch.setattr(c, "get_langchain_callbacks", Mock(return_value=[]))
        invoke = c.run_batch
    else:
        from lfx.components.llm_operations import lambda_filter as module

        c = module.LambdaFilterComponent(_user_id="runtime-owner", model=SELECTION, api_key="test-key")
        c.set_attributes(
            {"data": Message(text="abc"), "filter_instruction": "uppercase", "max_size": 5000, "sample_size": 500}
        )
        invoke = c._execute_lambda
    c._token_usage = None
    return SimpleNamespace(kind=request.param, module=module, component=c, invoke=invoke)


def model():
    from langchain_core.messages import AIMessage

    def response(text, input_tokens, output_tokens):
        return AIMessage(
            content=text,
            usage_metadata={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        )

    result = SimpleNamespace(
        abatch=AsyncMock(return_value=[response("one-output", 3, 4), response("two-output", 5, 6)]),
        ainvoke=AsyncMock(return_value=response("lambda text: text.upper()", 1, 2)),
        with_config=Mock(),
    )
    result.with_config.return_value = result
    return result


@pytest.mark.asyncio
async def test_operation_awaits_native_factory_and_preserves_output_usage(operation, monkeypatch):
    llm = model()
    loop = asyncio.get_running_loop()
    ticks = []
    finished = False

    async def heartbeat():
        while not finished:
            ticks.append(True)
            await asyncio.sleep(0.003)

    async def create(**kwargs):
        assert asyncio.get_running_loop() is loop
        assert kwargs["model"] == SELECTION
        assert kwargs["user_id"] == "runtime-owner"
        assert kwargs["api_key"] == "test-key"  # pragma: allowlist secret
        await asyncio.sleep(0.025)
        return llm

    factory = AsyncMock(side_effect=create)
    monkeypatch.setattr(operation.module, "aget_llm", factory)
    beat = asyncio.create_task(heartbeat())
    try:
        result = await operation.invoke()
    finally:
        finished = True
        await beat
    factory.assert_awaited_once()
    assert len(ticks) >= 3
    if operation.kind == "batch":
        assert result["model_response"].tolist() == ["one-output", "two-output"]
        # Preserve the baseline row merge; independently summing rows is a
        # separate correctness change from native factory dispatch.
        assert operation.component._token_usage.total_tokens == 11
        llm.abatch.assert_awaited_once()
    else:
        assert result == "ABC"
        assert operation.component._token_usage.total_tokens == 3
        llm.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancelled_factory_releases_lookup_before_model_work(operation, monkeypatch):
    entered = asyncio.Event()
    released = []

    async def create(**_kwargs):
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            released.append(True)

    monkeypatch.setattr(operation.module, "aget_llm", create)
    task = asyncio.create_task(operation.invoke())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert released == [True]


@pytest.mark.asyncio
@pytest.mark.parametrize("unavailable", [False, True])
async def test_real_factory_policy_stops_before_secret_or_vendor_import(operation, monkeypatch, unavailable):
    from lfx.base.models import unified_models

    failure = RuntimeError("policy unavailable") if unavailable else PermissionError("denied")
    snapshot = SimpleNamespace(require=Mock(side_effect=failure))
    resolve = AsyncMock(side_effect=failure) if unavailable else AsyncMock(return_value=snapshot)
    monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", resolve)
    secrets = AsyncMock(side_effect=AssertionError("secret lookup before denial"))
    vendor = Mock(side_effect=AssertionError("vendor import before denial"))
    monkeypatch.setattr(unified_models, "aget_api_key_for_provider", secrets)
    monkeypatch.setattr(unified_models, "get_model_class", vendor)
    with pytest.raises(type(failure)):
        await operation.invoke()
    secrets.assert_not_awaited()
    vendor.assert_not_called()

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from langflow.services.flow.flow_runner import LangflowRunnerExperimental


@pytest.fixture
def sample_flow_dict():
    return {
        "id": str(uuid4()),  # Add required ID field
        "name": "test_flow",  # Add name field
        "data": {
            "nodes": [],
            "edges": [],
        },
    }


@pytest.fixture
def flow_runner():
    return LangflowRunnerExperimental()


@pytest.mark.asyncio
async def test_database_exists_check(flow_runner, monkeypatch):
    """The runner derives initialization state from Alembic's current heads."""
    from langflow.services.flow import flow_runner as flow_runner_module

    probe = AsyncMock(side_effect=[("current_head",), ()])
    monkeypatch.setattr(flow_runner_module, "get_current_alembic_heads", probe)

    assert await flow_runner.database_exists_check() is True
    assert await flow_runner.database_exists_check() is False


@pytest.mark.asyncio
async def test_get_flow_dict_from_dict(flow_runner, sample_flow_dict):
    """Test loading flow from a dictionary."""
    result = await flow_runner.get_flow_dict(sample_flow_dict)
    assert result == sample_flow_dict


@pytest.mark.asyncio
async def test_get_flow_dict_invalid_input(flow_runner):
    """Test loading flow with invalid input type."""
    pattern = r"Input must be a file path .* or a JSON object .*"
    with pytest.raises(TypeError, match=pattern):
        await flow_runner.get_flow_dict(123)


@pytest.mark.asyncio
async def test_run_with_dict_input(flow_runner, sample_flow_dict):
    """Test running flow with dictionary input."""
    session_id = str(uuid4())
    input_value = "test input"

    result = await flow_runner.run(
        session_id=session_id,
        flow=sample_flow_dict,
        input_value=input_value,
    )
    assert result is not None


@pytest.mark.asyncio
async def test_run_with_different_input_types(flow_runner, sample_flow_dict):
    """Test running flow with different input and output types."""
    session_id = str(uuid4())
    test_cases = [
        ("text input", "text", "text"),
        ("chat input", "chat", "chat"),
        ("test input", "chat", "all"),  # Updated to use "all" as default output_type
    ]

    for input_value, input_type, output_type in test_cases:
        result = await flow_runner.run(
            session_id=session_id,
            flow=sample_flow_dict,
            input_value=input_value,
            input_type=input_type,
            output_type=output_type,
        )
        assert result is not None


@pytest.mark.asyncio
async def test_initialize_database(flow_runner, monkeypatch):
    """Test database initialization."""
    from langflow.services.flow import flow_runner as flow_runner_module

    database_exists_check = AsyncMock(return_value=False)
    initialize = AsyncMock()
    monkeypatch.setattr(flow_runner, "database_exists_check", database_exists_check)
    monkeypatch.setattr(flow_runner_module, "initialize_database", initialize)
    flow_runner.should_initialize_db = True

    await flow_runner.init_db_if_needed()

    database_exists_check.assert_awaited_once()
    initialize.assert_awaited_once_with(fix_migration=True)
    assert not flow_runner.should_initialize_db


@pytest.mark.parametrize("outcome", ["success", "error", "canceled", "keep"])
@pytest.mark.usefixtures("client")
async def test_default_runner_creates_active_identity_and_cleans_up(
    flow_runner, sample_flow_dict, monkeypatch, outcome
):
    """Local runs bind a real active user before tools and remove it on every exit."""
    import asyncio
    from types import SimpleNamespace

    from langflow.services.database.models.user.model import User
    from langflow.services.deps import get_auth_service, session_scope
    from lfx.base.tools.component_tool import _build_output_async_function
    from lfx.custom import Component
    from lfx.graph import Graph
    from lfx.io import Output

    observed = []

    class Counter(Component):
        outputs = [Output(name="result", display_name="Result", method="perform")]

        async def perform(self) -> str:
            return "tool ran"

    async def run_flow(**kwargs):
        user_id = kwargs["user_id"]
        await get_auth_service().validate_execution_user(user_id)
        observed.append(user_id)
        component = Counter()
        component.set_vertex(SimpleNamespace(graph=Graph(user_id=user_id)))
        assert await _build_output_async_function(component, component.perform)() == "tool ran"
        if outcome == "error":
            msg = "run failed"
            raise RuntimeError(msg)
        if outcome == "canceled":
            raise asyncio.CancelledError
        return "ok"

    monkeypatch.setattr(flow_runner, "init_db_if_needed", AsyncMock())
    monkeypatch.setattr(flow_runner, "prepare_flow_and_add_to_db", AsyncMock(return_value=sample_flow_dict))
    monkeypatch.setattr(flow_runner, "run_flow", run_flow)
    operation = flow_runner.run(
        session_id=str(uuid4()), flow=sample_flow_dict, input_value="hello", cleanup=outcome != "keep"
    )
    if outcome in {"success", "keep"}:
        assert await operation == "ok"
    else:
        exception = RuntimeError if outcome == "error" else asyncio.CancelledError
        with pytest.raises(exception):
            await operation
    assert len(observed) == 1
    async with session_scope() as session:
        retained = await session.get(User, UUID(observed[0]))
        if outcome == "keep":
            assert retained is not None
            assert retained.is_active
        else:
            assert retained is None
    if outcome == "keep":
        await flow_runner.clear_user_state(observed[0])


@pytest.mark.parametrize("generate_user", [False, True])
async def test_runner_preserves_explicit_identity_unless_generation_was_requested(
    flow_runner, sample_flow_dict, monkeypatch, generate_user
):
    """Explicit actors remain unchanged unless the caller requests a new identity."""
    from types import SimpleNamespace

    explicit_id, generated_id = str(uuid4()), str(uuid4())
    generate = AsyncMock(return_value=SimpleNamespace(id=generated_id))
    prepare = AsyncMock(return_value=sample_flow_dict)
    run = AsyncMock(return_value="ok")
    cleanup = AsyncMock()
    monkeypatch.setattr(flow_runner, "init_db_if_needed", AsyncMock())
    monkeypatch.setattr(flow_runner, "generate_user", generate)
    monkeypatch.setattr(flow_runner, "prepare_flow_and_add_to_db", prepare)
    monkeypatch.setattr(flow_runner, "run_flow", run)
    monkeypatch.setattr(flow_runner, "clear_user_state", cleanup)
    await flow_runner.run(
        session_id=str(uuid4()),
        flow=sample_flow_dict,
        input_value="hello",
        user_id=explicit_id,
        generate_user=generate_user,
    )
    expected = generated_id if generate_user else explicit_id
    assert prepare.await_args.kwargs["user_id"] == expected
    assert run.await_args.kwargs["user_id"] == expected
    cleanup.assert_awaited_once_with(user_id=expected)
    assert generate.await_count == int(generate_user)

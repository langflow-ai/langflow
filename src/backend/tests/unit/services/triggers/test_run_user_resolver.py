"""A registered plane may choose who runs a trigger's flow; OSS runs it as the trigger owner."""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.triggers.service import TriggerService, register_trigger_run_user_resolver


@pytest.fixture(autouse=True)
def _unregister():
    yield
    register_trigger_run_user_resolver(None)


async def test_nothing_registered_runs_as_the_trigger_owner() -> None:
    owner = uuid4()
    assert await TriggerService().resolve_run_user_id(None, flow_id=uuid4(), trigger_owner_id=owner) == owner


async def test_a_registered_resolver_picks_the_run_user_and_may_refuse() -> None:
    flow_id, owner, runner = uuid4(), uuid4(), uuid4()
    asked = []

    async def resolver(session, *, flow_id, trigger_owner_id):
        asked.append((session, flow_id, trigger_owner_id))
        return runner if flow_id == asked[0][1] else None

    register_trigger_run_user_resolver(resolver)
    service = TriggerService()
    assert await service.resolve_run_user_id("db", flow_id=flow_id, trigger_owner_id=owner) == runner
    assert asked == [("db", flow_id, owner)]
    assert await service.resolve_run_user_id("db", flow_id=uuid4(), trigger_owner_id=owner) is None


async def test_a_failing_resolver_raises_so_the_dispatcher_retries() -> None:
    async def resolver(*_args, **_kwargs):
        msg = "lookup failed"
        raise RuntimeError(msg)

    register_trigger_run_user_resolver(resolver)
    with pytest.raises(RuntimeError):
        await TriggerService().resolve_run_user_id(None, flow_id=uuid4(), trigger_owner_id=uuid4())


async def test_an_invalid_resolver_result_refuses_the_run() -> None:
    async def resolver(*_args, **_kwargs):
        return "invalid"

    register_trigger_run_user_resolver(resolver)
    assert await TriggerService().resolve_run_user_id(None, flow_id=uuid4(), trigger_owner_id=uuid4()) is None

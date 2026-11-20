"""Unit tests for the deletion hook registries in langflow.services.deletion_hooks."""

import uuid

import pytest
from fastapi import HTTPException
from langflow.services import deletion_hooks
from langflow.services.deletion_hooks import (
    DELETION_RESOURCES,
    RESOURCE_FILE,
    RESOURCE_FLOW,
    RESOURCE_KNOWLEDGE_BASE,
    RESOURCE_PROJECT,
    RESOURCE_VARIABLE,
    VIA_CASCADE,
    DeletionContext,
    register_post_deletion_hook,
    register_pre_deletion_hook,
    registered_post_deletion_hooks,
    registered_pre_deletion_hooks,
    run_post_deletion_after_commit,
    run_post_deletion_hooks,
    run_pre_deletion_hooks,
    wait_for_post_deletion_runs,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture(autouse=True)
def _clean_registry():
    pre = {resource: list(hooks) for resource, hooks in deletion_hooks._pre_deletion_hooks.items()}
    post = {resource: list(hooks) for resource, hooks in deletion_hooks._post_deletion_hooks.items()}
    yield
    for resource, hooks in pre.items():
        deletion_hooks._pre_deletion_hooks[resource][:] = hooks
    for resource, hooks in post.items():
        deletion_hooks._post_deletion_hooks[resource][:] = hooks


def _context(resource: str = RESOURCE_KNOWLEDGE_BASE, **kwargs) -> DeletionContext:
    return DeletionContext(resource=resource, resource_id=uuid.uuid4(), owner_id=uuid.uuid4(), name="docs", **kwargs)


def test_nothing_is_registered_by_default():
    for resource in DELETION_RESOURCES:
        assert registered_pre_deletion_hooks(resource) == []
        assert registered_post_deletion_hooks(resource) == []


def test_the_six_resources():
    assert set(DELETION_RESOURCES) == {"knowledge_base", "memory_base", "variable", "file", "project", "flow"}


@pytest.mark.parametrize("register", [register_pre_deletion_hook, register_post_deletion_hook])
def test_registering_twice_is_a_no_op_and_unknown_resources_fail_loudly(register):
    async def hook(_context):
        return None

    assert register(RESOURCE_VARIABLE, hook) is True
    assert register(RESOURCE_VARIABLE, hook) is False
    with pytest.raises(ValueError, match="Unknown"):
        register("variables", hook)


def test_the_two_registries_are_separate():
    async def hook(_context):
        return None

    register_pre_deletion_hook(RESOURCE_FILE, hook)
    assert registered_post_deletion_hooks(RESOURCE_FILE) == []


@pytest.mark.anyio
async def test_nothing_registered_means_both_runners_do_nothing():
    context = _context()
    await run_pre_deletion_hooks(context)
    await run_post_deletion_hooks(context)


@pytest.mark.anyio
async def test_pre_hooks_run_in_order_and_see_the_session_and_via():
    seen = []

    async def first(context):
        seen.append(("first", context.session, context.via))

    async def second(context):
        seen.append(("second", context.session, context.via))

    register_pre_deletion_hook(RESOURCE_KNOWLEDGE_BASE, first)
    register_pre_deletion_hook(RESOURCE_KNOWLEDGE_BASE, second)
    session = object()
    await run_pre_deletion_hooks(_context(session=session, via=VIA_CASCADE))
    assert seen == [("first", session, VIA_CASCADE), ("second", session, VIA_CASCADE)]


@pytest.mark.anyio
async def test_a_pre_hook_refusal_propagates_verbatim_and_stops_the_rest():
    ran = []

    async def refuse(_context):
        raise HTTPException(status_code=409, detail="in use")

    async def later(_context):
        ran.append("later")

    register_pre_deletion_hook(RESOURCE_KNOWLEDGE_BASE, refuse)
    register_pre_deletion_hook(RESOURCE_KNOWLEDGE_BASE, later)
    with pytest.raises(HTTPException) as caught:
        await run_pre_deletion_hooks(_context())
    assert caught.value.status_code == 409
    assert ran == []


@pytest.mark.anyio
async def test_a_broken_pre_hook_fails_closed():
    async def broken(_context):
        msg = "boom"
        raise RuntimeError(msg)

    register_pre_deletion_hook(RESOURCE_PROJECT, broken)
    with pytest.raises(RuntimeError, match="boom"):
        await run_pre_deletion_hooks(_context(RESOURCE_PROJECT))


@pytest.mark.anyio
async def test_post_hooks_never_see_a_session():
    seen = []

    async def hook(context):
        seen.append(context.session)

    register_post_deletion_hook(RESOURCE_FLOW, hook)
    await run_post_deletion_hooks(_context(RESOURCE_FLOW, session=object()))
    assert seen == [None]


@pytest.mark.anyio
async def test_a_post_hook_http_error_propagates_but_any_other_error_is_ignored():
    ran = []

    async def broken(_context):
        msg = "boom"
        raise RuntimeError(msg)

    async def after(_context):
        ran.append("after")

    register_post_deletion_hook(RESOURCE_FILE, broken)
    register_post_deletion_hook(RESOURCE_FILE, after)
    await run_post_deletion_hooks(_context(RESOURCE_FILE))
    assert ran == ["after"]

    async def loud(_context):
        raise HTTPException(status_code=500, detail="cleanup failed")

    register_post_deletion_hook(RESOURCE_PROJECT, loud)
    with pytest.raises(HTTPException):
        await run_post_deletion_hooks(_context(RESOURCE_PROJECT))


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with AsyncSession(engine, expire_on_commit=False) as db:
        yield db
    await engine.dispose()


@pytest.mark.anyio
async def test_after_commit_runs_the_hooks_once_the_session_committed(session):
    ran = []

    async def hook(context):
        ran.append((context.resource_id, context.session))

    register_post_deletion_hook(RESOURCE_FLOW, hook)
    context = _context(RESOURCE_FLOW, session=session)
    run_post_deletion_after_commit(session, context)
    await wait_for_post_deletion_runs()
    assert ran == []  # nothing before the commit

    await session.commit()
    await wait_for_post_deletion_runs()
    assert ran == [(context.resource_id, None)]

    await session.commit()  # a second commit does not run it again
    await wait_for_post_deletion_runs()
    assert len(ran) == 1


@pytest.mark.anyio
async def test_after_commit_forgets_the_event_when_the_session_rolls_back(session):
    ran = []

    async def hook(context):
        ran.append(context.resource_id)

    register_post_deletion_hook(RESOURCE_VARIABLE, hook)
    await session.exec(text("select 1"))  # a delete means a transaction is open
    run_post_deletion_after_commit(session, _context(RESOURCE_VARIABLE))
    await session.rollback()
    await session.commit()
    await wait_for_post_deletion_runs()
    assert ran == []


@pytest.mark.anyio
async def test_after_commit_logs_a_failing_hook_and_still_runs_the_next_event(session):
    ran = []

    async def hook(context):
        ran.append(context.name)
        if context.name == "a":
            raise HTTPException(status_code=500, detail="cleanup failed")

    register_post_deletion_hook(RESOURCE_FLOW, hook)
    run_post_deletion_after_commit(session, DeletionContext(RESOURCE_FLOW, uuid.uuid4(), name="a"))
    run_post_deletion_after_commit(session, DeletionContext(RESOURCE_FLOW, uuid.uuid4(), name="b"))
    await session.commit()
    await wait_for_post_deletion_runs()
    assert sorted(ran) == ["a", "b"]

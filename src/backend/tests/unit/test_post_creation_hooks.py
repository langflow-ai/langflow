"""Unit tests for the post-creation hook registry in langflow.services.creation_hooks."""

import uuid

import pytest
from fastapi import HTTPException
from langflow.services import creation_hooks
from langflow.services.creation_hooks import (
    POST_CREATION_RESOURCES,
    RESOURCE_KNOWLEDGE_BASE,
    RESOURCE_PROJECT,
    RESOURCE_VARIABLE,
    PostCreationContext,
    register_post_creation_hook,
    register_pre_creation_hook,
    registered_post_creation_hooks,
    run_post_creation_hooks,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    saved = {resource: list(hooks) for resource, hooks in creation_hooks._post_creation_hooks.items()}
    yield
    for resource, hooks in saved.items():
        creation_hooks._post_creation_hooks[resource][:] = hooks


def _context(resource: str = RESOURCE_KNOWLEDGE_BASE) -> PostCreationContext:
    return PostCreationContext(resource=resource, resource_id=uuid.uuid4(), owner_id=uuid.uuid4(), name="docs")


def test_nothing_is_registered_by_default():
    assert all(registered_post_creation_hooks(resource) == [] for resource in POST_CREATION_RESOURCES)


def test_registering_twice_is_a_no_op():
    async def hook(_context):
        return None

    assert register_post_creation_hook(RESOURCE_VARIABLE, hook) is True
    assert register_post_creation_hook(RESOURCE_VARIABLE, hook) is False
    assert registered_post_creation_hooks(RESOURCE_VARIABLE) == [hook]


def test_an_unknown_resource_fails_loudly_at_registration():
    async def hook(_context):
        return None

    with pytest.raises(ValueError, match="Unknown post-creation resource"):
        register_post_creation_hook("flow", hook)


def test_knowledge_base_and_variable_are_not_pre_creation_resources():
    """Registering a pre-creation hook for them would silently never run, so it must fail."""

    async def hook(_context):
        return None

    for resource in (RESOURCE_KNOWLEDGE_BASE, RESOURCE_VARIABLE):
        with pytest.raises(ValueError, match="Unknown pre-creation resource"):
            register_pre_creation_hook(resource, hook)
    with pytest.raises(ValueError, match="Unknown post-creation resource"):
        register_post_creation_hook(RESOURCE_PROJECT, hook)


@pytest.mark.asyncio
async def test_hooks_run_in_order_with_the_context_for_their_resource_only():
    seen: list[tuple[str, PostCreationContext]] = []

    async def first(context):
        seen.append(("first", context))

    async def second(context):
        seen.append(("second", context))

    async def other_resource(context):
        seen.append(("other", context))

    register_post_creation_hook(RESOURCE_KNOWLEDGE_BASE, first)
    register_post_creation_hook(RESOURCE_KNOWLEDGE_BASE, second)
    register_post_creation_hook(RESOURCE_VARIABLE, other_resource)
    context = _context()

    await run_post_creation_hooks(context)

    assert seen == [("first", context), ("second", context)]


@pytest.mark.asyncio
async def test_an_http_exception_from_a_hook_propagates_and_stops_the_rest():
    ran: list[str] = []

    async def failing(_context):
        raise HTTPException(status_code=500, detail="follow-up failed")

    async def after(_context):
        ran.append("after")

    register_post_creation_hook(RESOURCE_VARIABLE, failing)
    register_post_creation_hook(RESOURCE_VARIABLE, after)

    with pytest.raises(HTTPException) as excinfo:
        await run_post_creation_hooks(_context(RESOURCE_VARIABLE))

    assert excinfo.value.detail == "follow-up failed"
    assert ran == []


@pytest.mark.asyncio
async def test_any_other_exception_is_ignored_and_later_hooks_still_run():
    ran: list[str] = []

    async def broken(_context):
        msg = "boom"
        raise RuntimeError(msg)

    async def after(_context):
        ran.append("after")

    register_post_creation_hook(RESOURCE_KNOWLEDGE_BASE, broken)
    register_post_creation_hook(RESOURCE_KNOWLEDGE_BASE, after)

    await run_post_creation_hooks(_context())

    assert ran == ["after"]


@pytest.mark.asyncio
async def test_running_with_no_hooks_does_nothing():
    await run_post_creation_hooks(_context())

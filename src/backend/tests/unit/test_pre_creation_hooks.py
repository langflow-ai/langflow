"""Unit tests for the pre-creation hook registry in langflow.services.creation_hooks.

Testing library and framework: pytest
"""

import uuid

import pytest
from langflow.services.creation_hooks import (
    DENIED_STATUS_CODE,
    ERROR_CODE_FEATURE_NOT_IN_TIER,
    ERROR_CODE_HEADER,
    ERROR_CODE_TIER_LIMIT_REACHED,
    RESOURCE_PROJECT,
    RESOURCE_ROLE,
    RESOURCE_USER,
    RESOURCES,
    PreCreationContext,
    PreCreationDenied,
    _pre_creation_hooks,
    enforce_pre_creation,
    http_denial_error_code,
    pre_creation_denied_to_http,
    register_pre_creation_hook,
    registered_pre_creation_hooks,
    run_pre_creation_hooks,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Restore the module-global registry after each test."""
    saved = {resource: list(hooks) for resource, hooks in _pre_creation_hooks.items()}
    yield
    for resource, hooks in saved.items():
        _pre_creation_hooks[resource][:] = hooks


def _ctx(resource: str = RESOURCE_PROJECT) -> PreCreationContext:
    return PreCreationContext(resource=resource, actor_user_id=uuid.uuid4(), requested_name="My Project")


async def test_hooks_run_in_registration_order():
    calls: list[str] = []

    async def first(_context):
        calls.append("first")

    async def second(_context):
        calls.append("second")

    register_pre_creation_hook(RESOURCE_PROJECT, first)
    register_pre_creation_hook(RESOURCE_PROJECT, second)
    await run_pre_creation_hooks(_ctx())
    assert calls == ["first", "second"]


async def test_hook_receives_the_context():
    seen: list[PreCreationContext] = []

    async def capture(context):
        seen.append(context)

    register_pre_creation_hook(RESOURCE_USER, capture)
    context = PreCreationContext(resource=RESOURCE_USER, is_public_signup=True, requested_name="ada")
    await run_pre_creation_hooks(context)
    assert seen == [context]
    assert seen[0].is_public_signup is True
    assert seen[0].requested_name == "ada"


async def test_denial_short_circuits_later_hooks():
    calls: list[str] = []

    async def denying(_context):
        calls.append("denying")
        msg = "Your plan allows 3 projects."
        raise PreCreationDenied(msg, details={"resource": "projects", "limit": 3})

    async def never(_context):
        calls.append("never")

    register_pre_creation_hook(RESOURCE_PROJECT, denying)
    register_pre_creation_hook(RESOURCE_PROJECT, never)

    with pytest.raises(PreCreationDenied) as excinfo:
        await run_pre_creation_hooks(_ctx())

    assert calls == ["denying"]
    assert excinfo.value.error_code == ERROR_CODE_TIER_LIMIT_REACHED
    assert excinfo.value.details["limit"] == 3


async def test_non_denial_exception_fails_open_and_later_hooks_still_run():
    calls: list[str] = []

    async def broken(_context):
        msg = "boom"
        raise RuntimeError(msg)

    async def survivor(_context):
        calls.append("survivor")

    register_pre_creation_hook(RESOURCE_ROLE, broken)
    register_pre_creation_hook(RESOURCE_ROLE, survivor)

    # Must not raise: anything that is not a PreCreationDenied fails open.
    await run_pre_creation_hooks(_ctx(RESOURCE_ROLE))
    assert calls == ["survivor"]


async def test_unknown_resource_is_a_noop():
    await run_pre_creation_hooks(PreCreationContext(resource="no-such-resource"))


def test_registering_an_unknown_resource_raises():
    async def hook(_context):
        return None

    with pytest.raises(ValueError, match="Unknown pre-creation resource"):
        register_pre_creation_hook("workspace", hook)


def test_duplicate_registration_is_idempotent():
    async def hook(_context):
        return None

    assert register_pre_creation_hook(RESOURCE_USER, hook) is True
    assert register_pre_creation_hook(RESOURCE_USER, hook) is False
    assert registered_pre_creation_hooks(RESOURCE_USER) == [hook]


def test_registry_has_expected_resources():
    assert set(_pre_creation_hooks) == set(RESOURCES) == {"project", "user", "role"}


def test_registered_hooks_snapshot_is_a_copy():
    async def hook(_context):
        return None

    register_pre_creation_hook(RESOURCE_PROJECT, hook)
    snapshot = registered_pre_creation_hooks(RESOURCE_PROJECT)
    snapshot.clear()
    assert registered_pre_creation_hooks(RESOURCE_PROJECT) == [hook]
    assert registered_pre_creation_hooks("no-such-resource") == []


def test_http_mapping_for_a_numeric_limit():
    exc = pre_creation_denied_to_http(
        PreCreationDenied(
            "Your plan allows 3 projects. Upgrade to add more.",
            details={"resource": "projects", "limit": 3, "current": 3, "tier": "trial"},
        )
    )
    assert exc.status_code == DENIED_STATUS_CODE == 403
    assert exc.headers == {ERROR_CODE_HEADER: ERROR_CODE_TIER_LIMIT_REACHED}
    assert exc.detail == {
        "error_code": "tier_limit_reached",
        "message": "Your plan allows 3 projects. Upgrade to add more.",
        "resource": "projects",
        "limit": 3,
        "current": 3,
        "tier": "trial",
    }


def test_http_mapping_for_a_capability_gate():
    exc = pre_creation_denied_to_http(
        PreCreationDenied(
            "Custom roles are not part of your plan.",
            error_code=ERROR_CODE_FEATURE_NOT_IN_TIER,
            details={"feature": "custom_rbac_roles", "tier": None, "required_tiers": ["standard", "premium"]},
        )
    )
    assert exc.status_code == 403
    assert exc.headers == {ERROR_CODE_HEADER: ERROR_CODE_FEATURE_NOT_IN_TIER}
    assert exc.detail["error_code"] == "feature_not_in_tier"
    assert exc.detail["required_tiers"] == ["standard", "premium"]
    assert exc.detail["tier"] is None


def test_details_cannot_override_error_code_or_message():
    denied = PreCreationDenied(
        "the real message",
        details={"error_code": "spoofed", "message": "spoofed", "resource": "projects"},
    )
    assert denied.to_detail()["error_code"] == ERROR_CODE_TIER_LIMIT_REACHED
    assert denied.to_detail()["message"] == "the real message"
    assert denied.to_detail()["resource"] == "projects"


def test_empty_error_code_falls_back_to_the_limit_code():
    assert PreCreationDenied("nope", error_code="").error_code == ERROR_CODE_TIER_LIMIT_REACHED


async def test_enforce_pre_creation_maps_the_denial_to_http():
    from fastapi import HTTPException

    async def denying(_context):
        msg = "nope"
        raise PreCreationDenied(msg, details={"resource": "projects"})

    register_pre_creation_hook(RESOURCE_PROJECT, denying)
    with pytest.raises(HTTPException) as excinfo:
        await enforce_pre_creation(_ctx())
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail["message"] == "nope"


async def test_enforce_pre_creation_is_a_noop_without_hooks():
    await enforce_pre_creation(_ctx())


def test_context_is_frozen():
    from dataclasses import FrozenInstanceError

    context = _ctx()
    with pytest.raises(FrozenInstanceError):
        context.resource = "user"


async def test_an_http_exception_from_a_hook_is_not_swallowed():
    """A hook that answers with its own response stops the creation.

    The fail-open clause exists for *broken* hooks. A deliberate ``HTTPException``
    (the shape LE-2488's enterprise hook may use) must reach the client, or every
    limit written that way would silently allow the creation.
    """
    from fastapi import HTTPException

    calls: list[str] = []

    async def refusing(_context):
        calls.append("refusing")
        raise HTTPException(status_code=429, detail="too many projects")

    async def never(_context):
        calls.append("never")

    register_pre_creation_hook(RESOURCE_PROJECT, refusing)
    register_pre_creation_hook(RESOURCE_PROJECT, never)

    with pytest.raises(HTTPException) as excinfo:
        await run_pre_creation_hooks(_ctx())

    assert calls == ["refusing"]
    assert excinfo.value.status_code == 429


async def test_enforce_pre_creation_passes_a_hook_http_exception_through():
    from fastapi import HTTPException

    async def refusing(_context):
        raise HTTPException(status_code=402, detail={"error_code": "payment_required"})

    register_pre_creation_hook(RESOURCE_PROJECT, refusing)
    with pytest.raises(HTTPException) as excinfo:
        await enforce_pre_creation(_ctx())
    assert excinfo.value.status_code == 402
    assert excinfo.value.detail == {"error_code": "payment_required"}


def test_http_denial_error_code_reads_the_header_then_the_body():
    from fastapi import HTTPException

    from_header = HTTPException(
        status_code=403,
        detail={"error_code": "ignored_when_a_header_is_present"},
        headers={ERROR_CODE_HEADER: "tier_limit_reached"},
    )
    assert http_denial_error_code(from_header) == "tier_limit_reached"
    assert http_denial_error_code(HTTPException(status_code=403, detail={"error_code": "from_body"})) == "from_body"
    assert http_denial_error_code(HTTPException(status_code=403, detail="a plain string")) == "pre_creation_denied"

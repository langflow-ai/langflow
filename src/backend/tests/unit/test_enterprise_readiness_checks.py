"""Unit tests for the enterprise readiness check registry in health_check_router.

Testing library and framework: pytest
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from langflow.api.health_check_router import _enterprise_readiness_checks, healthz


@pytest.fixture(autouse=True)
def _clean_registry():
    """Restore the module-global registry after each test."""
    saved = list(_enterprise_readiness_checks)
    yield
    _enterprise_readiness_checks[:] = saved


@pytest.fixture
def fake_session():
    """Minimal async session double that satisfies the healthz DB probe."""
    exec_result = MagicMock()
    exec_result.first.return_value = None
    session = AsyncMock()
    session.exec = AsyncMock(return_value=exec_result)
    return session


@pytest.fixture
def _patch_services():
    """Patch get_chat_service and get_settings_service for healthz.

    Returns worker_timeout=300 to match the /health_check route's effective timeout.
    """
    fake_chat = AsyncMock()
    fake_settings = SimpleNamespace(settings=SimpleNamespace(worker_timeout=300))
    with (
        patch("langflow.api.health_check_router.get_chat_service", return_value=fake_chat),
        patch("langflow.api.health_check_router.get_settings_service", return_value=fake_settings),
    ):
        yield


# ---------------------------------------------------------------------------
# Registry state
# ---------------------------------------------------------------------------


def test_registry_is_empty_by_default():
    assert _enterprise_readiness_checks == []


# ---------------------------------------------------------------------------
# Registry: check callable contract — "ok" result
# ---------------------------------------------------------------------------


async def test_passing_check_returns_name_and_ok():
    async def always_ok():
        return ("entitlement", "ok")

    _enterprise_readiness_checks.append(always_ok)

    name, result = await _enterprise_readiness_checks[0]()
    assert name == "entitlement"
    assert result == "ok"
    assert not result.startswith("error:")


# ---------------------------------------------------------------------------
# Registry: check callable contract — "error:" result
# ---------------------------------------------------------------------------


async def test_error_check_result_starts_with_error_colon():
    async def failing_check():
        return ("entitlement", "error: entitlement lost")

    _enterprise_readiness_checks.append(failing_check)

    name, result = await _enterprise_readiness_checks[0]()
    assert name == "entitlement"
    assert result.startswith("error:")


# ---------------------------------------------------------------------------
# Registry: checks run in registration order
# ---------------------------------------------------------------------------


async def test_checks_run_in_registration_order():
    calls: list[str] = []

    async def first():
        calls.append("first")
        return ("a", "ok")

    async def second():
        calls.append("second")
        return ("b", "ok")

    _enterprise_readiness_checks.extend([first, second])

    for check in list(_enterprise_readiness_checks):
        await check()

    assert calls == ["first", "second"]


# ---------------------------------------------------------------------------
# /healthz handler behaviour — exercised via the real handler
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_patch_services")
async def test_healthz_returns_ok_with_empty_registry(fake_session):
    """No registered checks → healthy response."""
    response = await healthz(session=fake_session)
    assert response.status == "ok"
    assert response.db == "ok"
    assert response.chat == "ok"


@pytest.mark.usefixtures("_patch_services")
async def test_healthz_returns_ok_when_all_checks_pass(fake_session):
    """All registered checks succeed → healthy response."""

    async def always_ok():
        return ("entitlement", "ok")

    _enterprise_readiness_checks.append(always_ok)

    response = await healthz(session=fake_session)
    assert response.status == "ok"


@pytest.mark.usefixtures("_patch_services")
async def test_healthz_raises_503_on_error_result(fake_session):
    """A check returning 'error:…' causes a 503 with a generic detail."""

    async def failing_check():
        return ("entitlement", "error: entitlement lost")

    _enterprise_readiness_checks.append(failing_check)

    with pytest.raises(HTTPException) as exc_info:
        await healthz(session=fake_session)

    assert exc_info.value.status_code == 503
    # Detail must be generic — no plugin name or raw result exposed to clients.
    assert exc_info.value.detail == "Service unavailable"


@pytest.mark.usefixtures("_patch_services")
async def test_healthz_returns_ok_for_non_error_prefix_status(fake_session):
    """A check returning a non-'error:' status (e.g. 'errorless') must not trigger 503."""

    async def ambiguous_check():
        return ("entitlement", "errorless")

    _enterprise_readiness_checks.append(ambiguous_check)

    # Must complete successfully — 'errorless' does not start with 'error:'
    response = await healthz(session=fake_session)
    assert response.status == "ok"


@pytest.mark.usefixtures("_patch_services")
async def test_healthz_first_error_short_circuits_remaining_checks(fake_session):
    """The first error-result check stops further checks immediately."""
    calls: list[str] = []

    async def first_fail():
        calls.append("first")
        return ("check_a", "error: first failed")

    async def second():
        calls.append("second")
        return ("check_b", "ok")

    _enterprise_readiness_checks.extend([first_fail, second])

    with pytest.raises(HTTPException):
        await healthz(session=fake_session)

    assert "first" in calls
    assert "second" not in calls


@pytest.mark.usefixtures("_patch_services")
async def test_healthz_swallows_crashing_check(fake_session):
    """An exception from a check is logged and swallowed — no 503, no propagation."""

    async def boom():
        msg = "unexpected crash"
        raise RuntimeError(msg)

    _enterprise_readiness_checks.append(boom)

    # Must complete successfully — crash is swallowed.
    response = await healthz(session=fake_session)
    assert response.status == "ok"


@pytest.mark.usefixtures("_patch_services")
async def test_healthz_503_when_db_and_chat_fail(fake_session):
    """DB and chat failures → 500, not a 503 from the enterprise checks path."""
    fake_session.exec.side_effect = RuntimeError("db down")

    with pytest.raises(HTTPException) as exc_info:
        await healthz(session=fake_session)

    assert exc_info.value.status_code == 500


@pytest.mark.usefixtures("_patch_services")
async def test_healthz_raises_503_on_timeout(fake_session):
    """A check that remains pending longer than worker_timeout triggers a real asyncio timeout."""

    async def slow_check():
        # Waits on an Event that is never set — stays pending until cancelled.
        await asyncio.Event().wait()
        return ("entitlement", "ok")  # pragma: no cover

    _enterprise_readiness_checks.append(slow_check)

    with (
        patch(
            "langflow.api.health_check_router.get_settings_service",
            return_value=SimpleNamespace(settings=SimpleNamespace(worker_timeout=0.01)),
        ),
        pytest.raises(HTTPException) as exc_info,
    ):
        await healthz(session=fake_session)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Service unavailable"


@pytest.mark.usefixtures("_patch_services")
async def test_healthz_chat_failure_returns_500(fake_session):
    """Chat service failure (not DB) still causes 500 via has_error path."""
    with (
        patch("langflow.api.health_check_router.get_chat_service", side_effect=RuntimeError("chat down")),
        pytest.raises(HTTPException) as exc_info,
    ):
        await healthz(session=fake_session)

    assert exc_info.value.status_code == 500

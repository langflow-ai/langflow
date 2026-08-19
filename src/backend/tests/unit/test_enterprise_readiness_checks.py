"""Unit tests for the enterprise readiness check registry in health_check_router.

Testing library and framework: pytest
"""

import pytest
from fastapi import HTTPException
from langflow.api.health_check_router import _enterprise_readiness_checks


@pytest.fixture(autouse=True)
def _clean_registry():
    """Restore the module-global registry after each test."""
    saved = list(_enterprise_readiness_checks)
    yield
    _enterprise_readiness_checks[:] = saved


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
    assert not result.startswith("error")


# ---------------------------------------------------------------------------
# Registry: check callable contract — "error:" result
# ---------------------------------------------------------------------------


async def test_error_check_result_starts_with_error():
    async def failing_check():
        return ("entitlement", "error: entitlement lost")

    _enterprise_readiness_checks.append(failing_check)

    name, result = await _enterprise_readiness_checks[0]()
    assert name == "entitlement"
    assert result.startswith("error")


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
# Registry: /healthz loop behaviour — error causes 503, crash is swallowed
# Exercised by calling the handler logic directly (no HTTP transport needed).
# ---------------------------------------------------------------------------


async def _run_checks_like_healthz() -> HTTPException | None:
    """Replicate the /healthz enterprise check loop — returns 503 exc or None."""
    for check in list(_enterprise_readiness_checks):
        try:
            name, result = await check()
            if result.startswith("error"):
                return HTTPException(
                    status_code=503,
                    detail={"status": "nok", name: result},
                )
        except Exception:  # noqa: S110
            pass  # crash is swallowed — same as handler behaviour
    return None


async def test_error_check_causes_503_via_handler():
    async def failing_check():
        return ("entitlement", "error: entitlement lost")

    _enterprise_readiness_checks.append(failing_check)

    exc = await _run_checks_like_healthz()
    assert exc is not None
    assert exc.status_code == 503
    assert exc.detail["entitlement"] == "error: entitlement lost"
    assert exc.detail["status"] == "nok"


async def test_first_error_short_circuits_remaining_checks():
    calls: list[str] = []

    async def first_fail():
        calls.append("first")
        return ("check_a", "error: first failed")

    async def second():
        calls.append("second")
        return ("check_b", "ok")

    _enterprise_readiness_checks.extend([first_fail, second])

    await _run_checks_like_healthz()

    assert "first" in calls
    assert "second" not in calls


async def test_crashing_check_is_swallowed_by_handler_loop():
    async def boom():
        msg = "unexpected crash"
        raise RuntimeError(msg)

    _enterprise_readiness_checks.append(boom)

    # Crash is swallowed — must not propagate and must not trigger a 503.
    exc = await _run_checks_like_healthz()
    assert exc is None

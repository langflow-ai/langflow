"""Unit tests for the enterprise lifespan hook registry in langflow.main.

Testing library and framework: pytest
"""

import pytest
from langflow.main import _enterprise_lifespan_hooks, _run_enterprise_lifespan_hooks


@pytest.fixture(autouse=True)
def _clean_registry():
    """Restore the module-global registry after each test."""
    saved = {phase: list(hooks) for phase, hooks in _enterprise_lifespan_hooks.items()}
    yield
    for phase, hooks in saved.items():
        _enterprise_lifespan_hooks[phase][:] = hooks


async def test_hooks_run_in_registration_order():
    calls: list[str] = []

    async def first():
        calls.append("first")

    async def second():
        calls.append("second")

    _enterprise_lifespan_hooks["startup"].extend([first, second])
    await _run_enterprise_lifespan_hooks("startup")
    assert calls == ["first", "second"]


async def test_failing_hook_does_not_block_later_hooks():
    calls: list[str] = []

    async def broken():
        msg = "boom"
        raise RuntimeError(msg)

    async def survivor():
        calls.append("survivor")

    _enterprise_lifespan_hooks["shutdown"].extend([broken, survivor])
    # Must not raise: hooks are best-effort by contract.
    await _run_enterprise_lifespan_hooks("shutdown")
    assert calls == ["survivor"]


async def test_unknown_phase_is_a_noop():
    await _run_enterprise_lifespan_hooks("no-such-phase")


async def test_registry_has_expected_phases():
    assert set(_enterprise_lifespan_hooks) == {"startup", "shutdown"}

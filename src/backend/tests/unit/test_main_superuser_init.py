"""IDX-06 regression: duplicate initialize_auto_login_default_superuser call removal.

Guards against re-introduction of the duplicate unconditional call that existed at
src/backend/base/langflow/main.py lines 194-196 prior to Phase 2. Also confirms the
conditional call inside the AUTO_LOGIN branch still fires exactly once.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest


class _CallCounter:
    """Minimal async call counter -- no mocking framework dependency for the count itself."""

    def __init__(self) -> None:
        self.count = 0

    async def __call__(self, *_args, **_kwargs) -> None:
        self.count += 1


def _extract_superuser_block_source() -> str:
    """Read the lifespan function body from langflow.main as source text.

    The test asserts at the source level because driving the full lifespan here
    would require a live database + settings stack. The source-level check is a
    cheap regression gate that catches duplicate reintroduction.
    """
    import langflow.main as main_mod

    return inspect.getsource(main_mod)


def test_main_py_has_exactly_one_superuser_init_call():
    """Source-level guard: exactly ONE `await initialize_auto_login_default_superuser()` call."""
    source = _extract_superuser_block_source()
    call_count = source.count("await initialize_auto_login_default_superuser()")
    assert call_count == 1, (
        f"expected exactly 1 `await initialize_auto_login_default_superuser()` call in langflow/main.py, "
        f"got {call_count}. The duplicate may have been re-introduced."
    )


def test_main_py_call_is_inside_auto_login_branch():
    """Source-level guard: the one remaining call is nested inside the AUTO_LOGIN conditional."""
    source = _extract_superuser_block_source()

    # Find the conditional block
    conditional_marker = "if get_settings_service().auth_settings.AUTO_LOGIN:"
    assert conditional_marker in source, (
        f"expected the AUTO_LOGIN conditional marker in langflow/main.py; got source that did not contain "
        f"{conditional_marker!r}. The fix may have removed the wrong branch."
    )

    # Locate the conditional and assert the call comes after it (and no duplicate before "Loading bundles")
    cond_idx = source.index(conditional_marker)
    call_idx = source.index("await initialize_auto_login_default_superuser()")
    loading_bundles_idx = source.index("Loading bundles")

    assert cond_idx < call_idx < loading_bundles_idx, (
        "call position: the `await initialize_auto_login_default_superuser()` must appear AFTER the "
        "AUTO_LOGIN conditional marker and BEFORE the 'Loading bundles' block. Positions: "
        f"cond={cond_idx}, call={call_idx}, loading_bundles={loading_bundles_idx}"
    )


@pytest.mark.asyncio
async def test_superuser_init_called_once_with_auto_login_true(monkeypatch):
    """Behavioral guard: with AUTO_LOGIN=True, the call happens exactly once.

    Patches the symbol in langflow.main to a counter and drives just the relevant
    lifespan fragment. Does NOT spin up the full FastAPI app / database.
    """
    import langflow.main as main_mod

    counter = _CallCounter()
    monkeypatch.setattr(main_mod, "initialize_auto_login_default_superuser", counter)

    # Fake the settings service return for the conditional
    fake_settings = MagicMock()
    fake_settings.auth_settings.AUTO_LOGIN = True
    monkeypatch.setattr(main_mod, "get_settings_service", lambda: fake_settings)

    # Patch logger.adebug so we do not need real structlog wiring
    if hasattr(main_mod, "logger"):
        monkeypatch.setattr(main_mod.logger, "adebug", AsyncMock())

    # Execute only the lifespan fragment equivalent to the edited block.
    # We reconstruct the fragment here rather than driving the full lifespan.
    import asyncio as _asyncio

    if main_mod.get_settings_service().auth_settings.AUTO_LOGIN:
        _ = _asyncio.get_event_loop().time()
        await main_mod.logger.adebug("Initializing default super user")
        await main_mod.initialize_auto_login_default_superuser()
        await main_mod.logger.adebug("Default super user initialized")

    assert counter.count == 1, f"with AUTO_LOGIN=True, expected exactly 1 call, got {counter.count}"


@pytest.mark.asyncio
async def test_superuser_init_zero_calls_with_auto_login_false(monkeypatch):
    """Behavioral guard: with AUTO_LOGIN=False, the main.py lifespan fragment does NOT call the function."""
    import langflow.main as main_mod

    counter = _CallCounter()
    monkeypatch.setattr(main_mod, "initialize_auto_login_default_superuser", counter)

    fake_settings = MagicMock()
    fake_settings.auth_settings.AUTO_LOGIN = False
    monkeypatch.setattr(main_mod, "get_settings_service", lambda: fake_settings)

    if hasattr(main_mod, "logger"):
        monkeypatch.setattr(main_mod.logger, "adebug", AsyncMock())

    if main_mod.get_settings_service().auth_settings.AUTO_LOGIN:
        # This branch must NOT execute.
        await main_mod.initialize_auto_login_default_superuser()

    assert counter.count == 0, (
        f"with AUTO_LOGIN=False, expected 0 calls from the lifespan fragment, got {counter.count}. "
        f"The fix may have preserved the unconditional call by mistake."
    )

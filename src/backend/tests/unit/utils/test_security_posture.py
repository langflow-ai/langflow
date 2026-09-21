"""Unit tests for the custom-component execution security-posture warning (LE-2533)."""

from types import SimpleNamespace

import pytest
from langflow.utils import security_posture
from langflow.utils.security_posture import (
    CUSTOM_COMPONENT_EXECUTION_WARNING,
    custom_component_execution_warning,
    log_custom_component_execution_posture,
)


def _settings_service(*, auto_login: bool, allow_custom_components: bool, admin_only: bool):
    return SimpleNamespace(
        auth_settings=SimpleNamespace(AUTO_LOGIN=auto_login),
        settings=SimpleNamespace(
            allow_custom_components=allow_custom_components,
            custom_component_admin_only=admin_only,
        ),
    )


def test_warns_multi_user_permissive():
    """The exposed posture: multi-user, custom components on, not admin-only."""
    svc = _settings_service(auto_login=False, allow_custom_components=True, admin_only=False)
    assert custom_component_execution_warning(svc) == CUSTOM_COMPONENT_EXECUTION_WARNING


def test_warning_names_both_lockdowns():
    """Remediation must point at both settings so operators can pick either."""
    warning = custom_component_execution_warning(
        _settings_service(auto_login=False, allow_custom_components=True, admin_only=False)
    )
    assert "LANGFLOW_CUSTOM_COMPONENT_ADMIN_ONLY=true" in warning
    assert "LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false" in warning


def test_warning_scopes_the_sandbox_backend():
    """LANGFLOW_SANDBOX_BACKEND covers the interpreter components, not custom-component build.

    It is only consulted by ``lfx.components.tools.python_repl`` and
    ``lfx.components.utilities.python_repl_core``; custom component code is exec'd in the
    server process at build time, so the warning must not read as an alternative lockdown.
    """
    warning = custom_component_execution_warning(
        _settings_service(auto_login=False, allow_custom_components=True, admin_only=False)
    )
    assert "LANGFLOW_SANDBOX_BACKEND does not substitute" in warning
    assert "Python Interpreter and legacy Python REPL" in warning


def test_silent_single_user_default():
    """AUTO_LOGIN=true is the single-superuser default: no non-admin exists, so no warning."""
    svc = _settings_service(auto_login=True, allow_custom_components=True, admin_only=False)
    assert custom_component_execution_warning(svc) is None


def test_silent_when_admin_only():
    svc = _settings_service(auto_login=False, allow_custom_components=True, admin_only=True)
    assert custom_component_execution_warning(svc) is None


def test_silent_when_custom_components_disabled():
    svc = _settings_service(auto_login=False, allow_custom_components=False, admin_only=False)
    assert custom_component_execution_warning(svc) is None


@pytest.mark.parametrize("svc", [None, SimpleNamespace(), SimpleNamespace(auth_settings=None, settings=None)])
def test_missing_settings_never_raises(svc):
    """A partial/None settings service must degrade to no-warning, never raise at startup."""
    assert custom_component_execution_warning(svc) is None


def test_missing_attributes_use_model_defaults():
    """Absent attributes fall back to declared (permissive) defaults, so a bare multi-user object still warns."""
    svc = SimpleNamespace(auth_settings=SimpleNamespace(AUTO_LOGIN=False), settings=SimpleNamespace())
    assert custom_component_execution_warning(svc) == CUSTOM_COMPONENT_EXECUTION_WARNING


class _RecordingLogger:
    """Stand-in for the lfx logger that records calls and can simulate a failing log sink."""

    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls: list[tuple[str, str]] = []

    async def _log(self, level: str, message: str) -> None:
        self.calls.append((level, message))
        if self.fail:
            msg = "log sink closed"
            raise OSError(msg)

    async def awarning(self, message: str) -> None:
        await self._log("warning", message)

    async def adebug(self, message: str) -> None:
        await self._log("debug", message)


async def test_log_posture_warns_once_when_exposed(monkeypatch):
    recorder = _RecordingLogger()
    monkeypatch.setattr(security_posture, "logger", recorder)

    await log_custom_component_execution_posture(
        _settings_service(auto_login=False, allow_custom_components=True, admin_only=False)
    )

    assert recorder.calls == [("warning", CUSTOM_COMPONENT_EXECUTION_WARNING)]


async def test_log_posture_silent_when_locked_down(monkeypatch):
    recorder = _RecordingLogger()
    monkeypatch.setattr(security_posture, "logger", recorder)

    await log_custom_component_execution_posture(
        _settings_service(auto_login=False, allow_custom_components=True, admin_only=True)
    )

    assert recorder.calls == []


async def test_log_posture_never_raises_when_log_sink_fails(monkeypatch):
    """A broken sink fails the warning and the debug fallback alike; startup must still proceed."""
    recorder = _RecordingLogger(fail=True)
    monkeypatch.setattr(security_posture, "logger", recorder)

    await log_custom_component_execution_posture(
        _settings_service(auto_login=False, allow_custom_components=True, admin_only=False)
    )

    assert [level for level, _ in recorder.calls] == ["warning", "debug"]

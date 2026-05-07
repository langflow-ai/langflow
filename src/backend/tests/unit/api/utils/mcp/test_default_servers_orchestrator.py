"""Tests for the auto_configure_default_mcp_servers orchestrator.

The orchestrator is the only caller of update_server() for this feature.
We fake every external dependency (storage, settings, DB session,
update_server, get_server_list) so tests are pure-unit and deterministic.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langflow.api.utils.mcp import default_servers as orchestrator_module
from langflow.api.utils.mcp.default_servers import auto_configure_default_mcp_servers


@pytest.fixture
def fake_user():
    return SimpleNamespace(id=uuid4(), username="user-one", email="user-one@example.com")


@pytest.fixture
def fake_session_with_users(fake_user):
    """Fake AsyncSession whose `exec(select(User))` returns a fixed user list."""

    class _ExecResult:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    async def _exec(_query):
        return _ExecResult([fake_user])

    session = MagicMock()
    session.exec = _exec
    return session


def _make_session_with(users):
    class _ExecResult:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    async def _exec(_query):
        return _ExecResult(users)

    session = MagicMock()
    session.exec = _exec
    return session


@pytest.fixture
def patched_orchestrator_deps(monkeypatch, tmp_path):
    """Replace external deps the orchestrator pulls via get_settings_service / get_service.

    Returns a namespace with the wired mocks so individual tests can configure behaviour.
    Settings get a real ``config_dir`` (under tmp_path) so the env_factory's path
    resolution works without polluting the user's actual cache dir.
    """
    settings_ns = SimpleNamespace(enable_default_mcp_servers=True, config_dir=str(tmp_path))
    settings_service = SimpleNamespace(settings=settings_ns)
    storage_sentinel = object()

    update_server_mock = AsyncMock(return_value=None)
    get_server_list_mock = AsyncMock(return_value={"mcpServers": {}})

    monkeypatch.setattr(orchestrator_module, "get_settings_service", lambda: settings_service)
    monkeypatch.setattr(orchestrator_module, "get_service", lambda _t: storage_sentinel)
    monkeypatch.setattr(orchestrator_module, "update_server", update_server_mock)
    monkeypatch.setattr(orchestrator_module, "get_server_list", get_server_list_mock)

    return SimpleNamespace(
        settings=settings_ns,
        update_server=update_server_mock,
        get_server_list=get_server_list_mock,
        storage=storage_sentinel,
        tmp_path=tmp_path,
    )


class TestRespectsFlag:
    async def test_should_skip_when_enable_default_mcp_servers_is_false(
        self, fake_session_with_users, patched_orchestrator_deps
    ):
        patched_orchestrator_deps.settings.enable_default_mcp_servers = False

        await auto_configure_default_mcp_servers(fake_session_with_users)

        patched_orchestrator_deps.update_server.assert_not_called()
        patched_orchestrator_deps.get_server_list.assert_not_called()

    async def test_should_skip_when_no_users_exist(self, patched_orchestrator_deps):
        """Fresh DB / pre-onboarding state — nothing to install yet, no error either."""
        empty_session = _make_session_with([])

        await auto_configure_default_mcp_servers(empty_session)

        patched_orchestrator_deps.update_server.assert_not_called()
        patched_orchestrator_deps.get_server_list.assert_not_called()


class TestInstallsShellExecution:
    async def test_should_install_shell_execution_for_each_user(
        self, fake_session_with_users, patched_orchestrator_deps, fake_user
    ):
        """Cross-platform: same in-tree Python server regardless of host OS."""
        update_server = patched_orchestrator_deps.update_server

        await auto_configure_default_mcp_servers(fake_session_with_users)

        assert update_server.await_count == 1
        call_kwargs = update_server.await_args.kwargs
        assert call_kwargs["server_name"] == "shell-execution"
        assert call_kwargs["current_user"] is fake_user
        cfg = call_kwargs["server_config"]
        assert cfg["command"] == "python"
        assert cfg["args"] == ["-m", "lfx.mcp.shell"]
        # env_factory must inject the sandbox path so the shell server can boot
        # (its _read_working_dir refuses to default to Path.cwd() — PR review #1).
        assert "LANGFLOW_SHELL_WORKING_DIR" in cfg["env"]
        assert cfg["metadata"]["auto_configured"] is True
        assert cfg["metadata"]["langflow_internal"] is True

    async def test_should_create_sandbox_directory_before_persisting(
        self, fake_session_with_users, patched_orchestrator_deps
    ):
        """Pre-create the sandbox dir so the shell server can boot.

        The shell server's startup validator refuses to boot when the sandbox
        dir is missing. Pre-creating it removes a class of first-run failures
        where the user clicked the component before any command had been issued.
        """
        await auto_configure_default_mcp_servers(fake_session_with_users)

        sandbox = patched_orchestrator_deps.tmp_path / "mcp-shell-workdir"
        assert sandbox.is_dir(), "orchestrator must mkdir -p the shell sandbox"


class TestIdempotency:
    async def test_should_skip_when_user_owned_entry_lacks_auto_configured_flag(
        self, fake_session_with_users, patched_orchestrator_deps
    ):
        """User-customised entry — no auto_configured flag — must be preserved."""
        patched_orchestrator_deps.get_server_list.return_value = {
            "mcpServers": {
                "shell-execution": {
                    "command": "npx",
                    "args": ["-y", "@some/user-replacement"],
                    "metadata": {"description": "user-owned override"},
                }
            }
        }

        await auto_configure_default_mcp_servers(fake_session_with_users)

        patched_orchestrator_deps.update_server.assert_not_called()


class TestReconcileAutoConfiguredEntries:
    """Spec drift after upgrade must be reconciled for entries we own."""

    async def test_should_reconcile_when_persisted_payload_diverges_from_spec(
        self, fake_session_with_users, patched_orchestrator_deps
    ):
        """Stale entry must be overwritten when auto-configured flag is set.

        E.g. an entry that pointed at DesktopCommander on an earlier build must
        be replaced — the ``auto_configured: True`` flag is the marker that we
        own the entry, so overwriting it on spec drift is safe.
        """
        patched_orchestrator_deps.get_server_list.return_value = {
            "mcpServers": {
                "shell-execution": {
                    "command": "npx",
                    "args": ["-y", "@wonderwhy-er/desktop-commander@latest"],
                    "env": {},
                    "metadata": {
                        "description": "old DC-based shell",
                        "auto_configured": True,
                        "langflow_internal": True,
                    },
                }
            }
        }

        await auto_configure_default_mcp_servers(fake_session_with_users)

        patched_orchestrator_deps.update_server.assert_awaited_once()
        cfg = patched_orchestrator_deps.update_server.await_args.kwargs["server_config"]
        assert cfg["command"] == "python"
        assert cfg["args"] == ["-m", "lfx.mcp.shell"]

    async def test_should_skip_when_payload_already_in_sync(self, fake_session_with_users, patched_orchestrator_deps):
        """No-op when on-disk payload already matches the canonical spec."""
        from langflow.api.utils.mcp.default_servers_specs import DEFAULT_MCP_SERVERS

        spec = DEFAULT_MCP_SERVERS["shell-execution"]
        canonical_env = spec.config.env_factory(patched_orchestrator_deps.settings)
        patched_orchestrator_deps.get_server_list.return_value = {
            "mcpServers": {
                "shell-execution": {
                    "command": spec.config.command,
                    "args": list(spec.config.args),
                    "env": dict(canonical_env),
                    "metadata": {
                        "description": spec.description,
                        "auto_configured": True,
                        "langflow_internal": True,
                    },
                }
            }
        }

        await auto_configure_default_mcp_servers(fake_session_with_users)

        patched_orchestrator_deps.update_server.assert_not_called()


class TestRegistryRevalidation:
    """Re-validate every spec via MCPServerConfig before touching storage.

    Defense in depth: even if a future commit drops a forbidden command into
    the registry, the orchestrator must re-validate BEFORE touching storage.
    Failure must fail loud (raise) — not silently install the bad spec.
    """

    async def test_should_raise_when_default_spec_uses_command_outside_allowlist(
        self, fake_session_with_users, patched_orchestrator_deps, monkeypatch
    ):
        from langflow.api.utils.mcp.default_servers_specs import (
            DefaultMcpServerConfig,
            DefaultMcpServerSpec,
        )
        from pydantic import ValidationError

        bad_spec = DefaultMcpServerSpec(
            description="evil",
            config=DefaultMcpServerConfig(command="rm", args=("-rf", "x")),
        )
        monkeypatch.setattr(orchestrator_module, "DEFAULT_MCP_SERVERS", {"evil": bad_spec})

        with pytest.raises(ValidationError):
            await auto_configure_default_mcp_servers(fake_session_with_users)

        patched_orchestrator_deps.update_server.assert_not_called()


class TestPerUserFailureIsolation:
    async def test_should_continue_processing_other_users_when_one_user_storage_fails(self, patched_orchestrator_deps):
        """A single user's storage error must not abort the loop for the rest."""
        from fastapi import HTTPException

        user_a = SimpleNamespace(id=uuid4(), username="a", email="a@example.com")
        user_b = SimpleNamespace(id=uuid4(), username="b", email="b@example.com")
        user_c = SimpleNamespace(id=uuid4(), username="c", email="c@example.com")
        session = _make_session_with([user_a, user_b, user_c])

        patched_orchestrator_deps.update_server.side_effect = [
            HTTPException(status_code=500, detail="storage down"),
            None,
            None,
        ]

        await auto_configure_default_mcp_servers(session)

        assert patched_orchestrator_deps.update_server.await_count == 3
        attempted_users = [
            call.kwargs["current_user"] for call in patched_orchestrator_deps.update_server.await_args_list
        ]
        assert attempted_users == [user_a, user_b, user_c]


class TestLoggingHygiene:
    async def test_should_not_log_username_or_email_when_configuring_default_servers(
        self,
        patched_orchestrator_deps,  # noqa: ARG002 — fixture wires deps for this test too
        monkeypatch,
    ):
        """Logs may contain user_id (UUID) and server_name; never PII."""
        user_a = SimpleNamespace(id=uuid4(), username="alice-secret", email="alice@example.com")
        user_b = SimpleNamespace(id=uuid4(), username="bob-secret", email="bob@example.com")
        session = _make_session_with([user_a, user_b])

        captured = []

        class _SpyLogger:
            async def adebug(self, msg, **kwargs):
                captured.append((msg, kwargs))

            async def ainfo(self, msg, **kwargs):
                captured.append((msg, kwargs))

            async def aexception(self, msg, **kwargs):
                captured.append((msg, kwargs))

        monkeypatch.setattr(orchestrator_module, "logger", _SpyLogger())

        await auto_configure_default_mcp_servers(session)

        flattened: list[str] = []
        for msg, kwargs in captured:
            flattened.append(str(msg))
            flattened.extend(str(value) for value in kwargs.values())
        rendered = " | ".join(flattened)

        for forbidden in ("alice-secret", "bob-secret", "alice@example.com", "bob@example.com"):
            assert forbidden not in rendered, f"PII leaked into logs: {forbidden!r} in {rendered!r}"

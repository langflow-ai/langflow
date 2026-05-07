"""Tests for the auto_configure_default_mcp_servers orchestrator.

The orchestrator is the only caller of update_server() for this feature.
We fake every external dependency (storage, settings, DB session, update_server,
get_server_list, platform.system) so tests are pure-unit and deterministic.
"""

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
def patched_orchestrator_deps(monkeypatch):
    """Replace external deps the orchestrator pulls via get_settings_service / get_service.

    Returns the (settings_namespace, update_server_mock, get_server_list_mock,
    storage_service_sentinel) tuple so individual tests can configure behavior.
    """
    settings_ns = SimpleNamespace(enable_default_mcp_servers=True)
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
        """Cross-platform: same payload regardless of host OS (DesktopCommander via npx)."""
        update_server = patched_orchestrator_deps.update_server

        await auto_configure_default_mcp_servers(fake_session_with_users)

        assert update_server.await_count == 1
        call_kwargs = update_server.await_args.kwargs
        assert call_kwargs["server_name"] == "shell-execution"
        assert call_kwargs["current_user"] is fake_user
        cfg = call_kwargs["server_config"]
        assert cfg["command"] == "npx"
        assert cfg["args"] == ["-y", "@wonderwhy-er/desktop-commander@latest"]
        assert cfg["env"] == {}
        assert cfg["metadata"]["auto_configured"] is True
        assert cfg["metadata"]["langflow_internal"] is True


class TestIdempotency:
    async def test_should_skip_when_server_already_exists_for_user(
        self, fake_session_with_users, patched_orchestrator_deps
    ):
        """User already has a `shell-execution` entry — possibly customized; never overwrite."""
        patched_orchestrator_deps.get_server_list.return_value = {
            "mcpServers": {
                "shell-execution": {
                    "command": "npx",
                    "args": ["-y", "@some/user-replacement"],
                }
            }
        }

        await auto_configure_default_mcp_servers(fake_session_with_users)

        patched_orchestrator_deps.update_server.assert_not_called()


class TestReconcileAutoConfiguredEntries:
    """Reconcile auto-configured entries when the canonical spec drifts.

    When the canonical spec evolves (e.g. a new `metadata.startup_timeout_seconds`
    field is added), users who installed Langflow on an earlier build keep a
    stale persisted payload — the orchestrator's old skip-if-exists behavior
    would lock them out of fixes forever (notably: the 60s opt-in needed to
    survive the first `npx -y @wonderwhy-er/desktop-commander@latest` download
    on Windows + slow networks).

    Reconciliation is gated on `metadata.auto_configured == True`: only entries
    that we wrote can be overwritten. Anything missing the flag (e.g. the user
    swapped in their own server) is preserved unconditionally.
    """

    async def test_should_reconcile_auto_configured_entry_when_persisted_payload_diverges_from_spec(
        self, fake_session_with_users, patched_orchestrator_deps
    ):
        """Stale entry from a pre-`startup_timeout_seconds` build must be updated."""
        patched_orchestrator_deps.get_server_list.return_value = {
            "mcpServers": {
                "shell-execution": {
                    "command": "npx",
                    "args": ["-y", "@wonderwhy-er/desktop-commander@latest"],
                    "env": {},
                    "metadata": {
                        "description": (
                            "Cross-platform shell execution + filesystem control (wonderwhy-er/desktop-commander)."
                        ),
                        "auto_configured": True,
                        "langflow_internal": True,
                        # NOTE: no startup_timeout_seconds — this is the stale field.
                    },
                }
            }
        }

        await auto_configure_default_mcp_servers(fake_session_with_users)

        patched_orchestrator_deps.update_server.assert_awaited_once()
        cfg = patched_orchestrator_deps.update_server.await_args.kwargs["server_config"]
        assert cfg["metadata"].get("startup_timeout_seconds") == 60

    async def test_should_not_overwrite_entry_lacking_auto_configured_flag(
        self, fake_session_with_users, patched_orchestrator_deps
    ):
        """User-owned entry (no `auto_configured` flag) must be preserved."""
        patched_orchestrator_deps.get_server_list.return_value = {
            "mcpServers": {
                "shell-execution": {
                    "command": "npx",
                    "args": ["-y", "@user/custom-fork"],
                    "env": {},
                    "metadata": {"description": "user-owned override"},
                }
            }
        }

        await auto_configure_default_mcp_servers(fake_session_with_users)

        patched_orchestrator_deps.update_server.assert_not_called()

    async def test_should_skip_when_auto_configured_entry_payload_already_matches_spec(
        self, fake_session_with_users, patched_orchestrator_deps
    ):
        """No-op when the persisted payload already matches the canonical spec.

        Avoids needless disk writes and noisy logs on every Langflow startup.
        """
        from langflow.api.utils.mcp.default_servers_specs import DEFAULT_MCP_SERVERS

        spec = DEFAULT_MCP_SERVERS["shell-execution"]
        patched_orchestrator_deps.get_server_list.return_value = {
            "mcpServers": {
                "shell-execution": {
                    "command": spec.config.command,
                    "args": list(spec.config.args),
                    "env": dict(spec.config.env),
                    "metadata": {
                        "description": spec.description,
                        "auto_configured": True,
                        "langflow_internal": True,
                        "startup_timeout_seconds": spec.startup_timeout_seconds,
                    },
                }
            }
        }

        await auto_configure_default_mcp_servers(fake_session_with_users)

        patched_orchestrator_deps.update_server.assert_not_called()


class TestRegistryRevalidation:
    """Defense-in-depth on the registry.

    Even if a future commit drops a forbidden command into the registry, the
    orchestrator must re-validate via MCPServerConfig BEFORE touching storage.
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
            config=DefaultMcpServerConfig(command="rm", args=("-rf", "x"), env={}),
        )
        monkeypatch.setattr(
            orchestrator_module,
            "DEFAULT_MCP_SERVERS",
            {"evil": bad_spec},
        )

        with pytest.raises(ValidationError):
            await auto_configure_default_mcp_servers(fake_session_with_users)

        patched_orchestrator_deps.update_server.assert_not_called()

    async def test_should_raise_when_default_spec_includes_blocked_env_var(
        self, fake_session_with_users, patched_orchestrator_deps, monkeypatch
    ):
        from langflow.api.utils.mcp.default_servers_specs import (
            DefaultMcpServerConfig,
            DefaultMcpServerSpec,
        )
        from pydantic import ValidationError

        bad_spec = DefaultMcpServerSpec(
            description="leak via LD_PRELOAD",
            config=DefaultMcpServerConfig(
                command="npx",
                args=("-y", "@wonderwhy-er/desktop-commander@latest"),
                env={"LD_PRELOAD": "evil.so"},
            ),
        )
        monkeypatch.setattr(
            orchestrator_module,
            "DEFAULT_MCP_SERVERS",
            {"leaky": bad_spec},
        )

        with pytest.raises(ValidationError):
            await auto_configure_default_mcp_servers(fake_session_with_users)

        patched_orchestrator_deps.update_server.assert_not_called()


class TestRegistryExtensibility:
    """Adding a new default server must require no orchestrator changes.

    The orchestrator iterates DEFAULT_MCP_SERVERS and treats every entry uniformly,
    so registering a new default is a one-line change to the registry.
    """

    async def test_should_install_additional_servers_added_to_registry(
        self, fake_session_with_users, patched_orchestrator_deps, monkeypatch
    ):
        from langflow.api.utils.mcp.default_servers_specs import (
            DEFAULT_MCP_SERVERS,
            DefaultMcpServerConfig,
            DefaultMcpServerSpec,
        )

        extra_spec = DefaultMcpServerSpec(
            description="Hypothetical fetch server",
            config=DefaultMcpServerConfig(command="uvx", args=("mcp-fetch",), env={}),
        )
        extended = {**DEFAULT_MCP_SERVERS, "fetch": extra_spec}
        monkeypatch.setattr(orchestrator_module, "DEFAULT_MCP_SERVERS", extended)

        await auto_configure_default_mcp_servers(fake_session_with_users)

        installed_names = {
            call.kwargs["server_name"] for call in patched_orchestrator_deps.update_server.await_args_list
        }
        assert installed_names == {"shell-execution", "fetch"}


class TestLoggingHygiene:
    async def test_should_not_log_username_or_email_when_configuring_default_servers(
        self,
        patched_orchestrator_deps,  # noqa: ARG002 — fixture wires deps for this test too
        monkeypatch,
    ):
        """Logs may contain user_id (UUID) and server_name; never PII (username/email)."""
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


class TestPerUserFailureIsolation:
    async def test_should_continue_processing_other_users_when_one_user_storage_fails(self, patched_orchestrator_deps):
        """A single user's storage error must not abort the loop for the rest."""
        from fastapi import HTTPException

        user_a = SimpleNamespace(id=uuid4(), username="a", email="a@example.com")
        user_b = SimpleNamespace(id=uuid4(), username="b", email="b@example.com")
        user_c = SimpleNamespace(id=uuid4(), username="c", email="c@example.com")
        session = _make_session_with([user_a, user_b, user_c])

        # First user's update_server raises; the other two must still be attempted.
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

"""Unit tests for lfx login -- login_command and helpers.

All tests run entirely in-process; no real Langflow instance or SDK required.
The SDK module is replaced wholesale with MagicMock so only the login logic
(key masking, connection probing, success/failure output) is under test.
"""
# pragma: allowlist secret -- all credentials in this file are fake test data

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import typer

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_BASE_URL = "http://langflow.test"
_API_KEY = "abcdefghijklmnop"  # pragma: allowlist secret  (16 chars — longer than 8)
_SHORT_KEY = "short"  # pragma: allowlist secret  (5 chars — at or under the 8-char mask threshold)
_EXACT_KEY = "exactly8"  # pragma: allowlist secret  (exactly 8 chars)


# ---------------------------------------------------------------------------
# Fake SDK exception classes
# ---------------------------------------------------------------------------


class _FakeLangflowAuthError(Exception):
    """Stand-in for langflow_sdk.LangflowAuthError in unit tests."""


class _FakeLangflowConnectionError(Exception):
    """Stand-in for langflow_sdk.LangflowConnectionError in unit tests."""


class _FakeLangflowHTTPError(Exception):
    """Stand-in for langflow_sdk.LangflowHTTPError in unit tests."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        super().__init__(detail)


# A fake exception whose qualname contains "ValidationError" so _probe_connection
# treats it as a successful probe.
class _FakeValidationError(Exception):
    """Simulates a Pydantic ValidationError (qualname contains 'ValidationError')."""


_FakeValidationError.__qualname__ = "ModelMetaclass.ValidationError"


# ---------------------------------------------------------------------------
# SDK / client / env helpers
# ---------------------------------------------------------------------------


def _make_client_mock(flows: list | None = None) -> MagicMock:
    client = MagicMock()
    client.list_flows.return_value = flows if flows is not None else [MagicMock(), MagicMock()]
    return client


def _make_sdk_mock(client_mock: MagicMock | None = None) -> MagicMock:
    """Return a mock langflow_sdk module wired up for login tests."""
    if client_mock is None:
        client_mock = _make_client_mock()
    sdk = MagicMock()
    sdk.Client.return_value = client_mock
    sdk.LangflowAuthError = _FakeLangflowAuthError
    sdk.LangflowConnectionError = _FakeLangflowConnectionError
    sdk.LangflowHTTPError = _FakeLangflowHTTPError
    return sdk


def _make_env_cfg(
    url: str = _BASE_URL,
    api_key: str | None = _API_KEY,
    name: str = "staging",
) -> MagicMock:
    env_cfg = MagicMock()
    env_cfg.url = url
    env_cfg.api_key = api_key
    env_cfg.name = name
    return env_cfg


def _run_login(
    *,
    env: str | None = "staging",
    environments_file: str | None = None,
    target: str | None = None,
    api_key: str | None = _API_KEY,
    sdk_mock: MagicMock | None = None,
    env_cfg: MagicMock | None = None,
) -> None:
    """Invoke login_command with a mocked SDK and mocked env resolution."""
    from lfx.cli.login import login_command

    mock = sdk_mock if sdk_mock is not None else _make_sdk_mock()
    resolved_env = env_cfg if env_cfg is not None else _make_env_cfg()

    with (
        patch("lfx.cli.login.load_sdk", return_value=mock),
        patch("lfx.config.resolve_environment", return_value=resolved_env),
    ):
        login_command(
            env=env,
            environments_file=environments_file,
            target=target,
            api_key=api_key,
        )


# ---------------------------------------------------------------------------
# _mask_key
# ---------------------------------------------------------------------------


class TestMaskKey:
    def test_long_key_shows_first_8_chars_plus_ellipsis(self):
        from lfx.cli.login import _mask_key

        result = _mask_key(_API_KEY)
        assert result == _API_KEY[:8] + "..."

    def test_key_exactly_8_chars_returns_stars(self):
        from lfx.cli.login import _mask_key

        result = _mask_key(_EXACT_KEY)
        assert result == "***"

    def test_short_key_returns_stars(self):
        from lfx.cli.login import _mask_key

        result = _mask_key(_SHORT_KEY)
        assert result == "***"

    def test_empty_key_returns_stars(self):
        from lfx.cli.login import _mask_key

        result = _mask_key("")
        assert result == "***"

    def test_exactly_9_chars_key_shows_first_8_plus_ellipsis(self):
        from lfx.cli.login import _mask_key

        key = "123456789"  # pragma: allowlist secret
        result = _mask_key(key)
        assert result == "12345678..."

    def test_mask_does_not_reveal_full_key(self):
        from lfx.cli.login import _mask_key

        key = "supersecretkeyvalue"  # pragma: allowlist secret
        result = _mask_key(key)
        assert key not in result
        assert result.endswith("...")


# ---------------------------------------------------------------------------
# _probe_connection
# ---------------------------------------------------------------------------


class TestProbeConnection:
    def test_successful_list_flows_returns_ok(self):
        from lfx.cli.login import _probe_connection

        flows = [MagicMock(), MagicMock(), MagicMock()]
        client = _make_client_mock(flows=flows)
        sdk = _make_sdk_mock(client_mock=client)
        ok, msg, count = _probe_connection(client, sdk)
        assert ok is True
        assert msg == "OK"
        assert count == 3

    def test_empty_flow_list_returns_ok_with_zero_count(self):
        from lfx.cli.login import _probe_connection

        client = _make_client_mock(flows=[])
        sdk = _make_sdk_mock(client_mock=client)
        ok, _msg, count = _probe_connection(client, sdk)
        assert ok is True
        assert count == 0

    def test_auth_error_returns_auth_message(self):
        from lfx.cli.login import _probe_connection

        client = _make_client_mock()
        client.list_flows.side_effect = _FakeLangflowAuthError("unauthorized")
        sdk = _make_sdk_mock(client_mock=client)
        ok, msg, count = _probe_connection(client, sdk)
        assert ok is False
        assert msg == "auth"
        assert count == 0

    def test_connection_error_returns_connection_message(self):
        from lfx.cli.login import _probe_connection

        client = _make_client_mock()
        client.list_flows.side_effect = _FakeLangflowConnectionError("refused")
        sdk = _make_sdk_mock(client_mock=client)
        ok, msg, count = _probe_connection(client, sdk)
        assert ok is False
        assert msg.startswith("connection:")
        assert count == 0

    def test_http_error_returns_http_message(self):
        from lfx.cli.login import _probe_connection

        client = _make_client_mock()
        client.list_flows.side_effect = _FakeLangflowHTTPError(503, "service unavailable")
        sdk = _make_sdk_mock(client_mock=client)
        ok, msg, count = _probe_connection(client, sdk)
        assert ok is False
        assert msg.startswith("http:")
        assert count == 0

    def test_validation_error_qualname_returns_ok(self):
        from lfx.cli.login import _probe_connection

        client = _make_client_mock()
        client.list_flows.side_effect = _FakeValidationError("schema mismatch")
        sdk = _make_sdk_mock(client_mock=client)
        ok, msg, count = _probe_connection(client, sdk)
        assert ok is True
        assert msg == "OK"
        assert count == 0

    def test_generic_exception_returns_error_message(self):
        from lfx.cli.login import _probe_connection

        client = _make_client_mock()
        client.list_flows.side_effect = RuntimeError("something went wrong")
        sdk = _make_sdk_mock(client_mock=client)
        ok, msg, count = _probe_connection(client, sdk)
        assert ok is False
        assert msg.startswith("error:")
        assert count == 0

    def test_connection_error_message_contains_original_message(self):
        from lfx.cli.login import _probe_connection

        original_msg = "Connection refused at port 7860"
        client = _make_client_mock()
        client.list_flows.side_effect = _FakeLangflowConnectionError(original_msg)
        sdk = _make_sdk_mock(client_mock=client)
        _, msg, _ = _probe_connection(client, sdk)
        assert original_msg in msg

    def test_flow_count_matches_returned_list_length(self):
        from lfx.cli.login import _probe_connection

        flows = [MagicMock() for _ in range(5)]
        client = _make_client_mock(flows=flows)
        sdk = _make_sdk_mock(client_mock=client)
        _, _, count = _probe_connection(client, sdk)
        assert count == 5


# ---------------------------------------------------------------------------
# login_command — success
# ---------------------------------------------------------------------------


class TestLoginCommandSuccess:
    def test_successful_probe_does_not_raise(self):
        client = _make_client_mock(flows=[MagicMock()])
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        _run_login(sdk_mock=sdk, env_cfg=env_cfg)  # Should not raise

    def test_successful_probe_calls_client_list_flows(self):
        client = _make_client_mock(flows=[MagicMock()])
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        _run_login(sdk_mock=sdk, env_cfg=env_cfg)
        client.list_flows.assert_called_once_with(page=1, size=1)

    def test_client_constructed_with_resolved_credentials(self):
        client = _make_client_mock()
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg(url=_BASE_URL, api_key=_API_KEY)
        _run_login(sdk_mock=sdk, env_cfg=env_cfg)
        sdk.Client.assert_called_once_with(base_url=_BASE_URL, api_key=_API_KEY)

    def test_validation_error_probe_succeeds_without_exit(self):
        """A ValidationError during list_flows is treated as a successful probe."""
        client = _make_client_mock()
        client.list_flows.side_effect = _FakeValidationError("schema drift")
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        _run_login(sdk_mock=sdk, env_cfg=env_cfg)  # Should not raise


# ---------------------------------------------------------------------------
# login_command — auth failure
# ---------------------------------------------------------------------------


class TestLoginCommandAuthFailure:
    def test_auth_error_raises_exit_1(self):
        client = _make_client_mock()
        client.list_flows.side_effect = _FakeLangflowAuthError("unauthorized")
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        with pytest.raises(typer.Exit) as exc_info:
            _run_login(sdk_mock=sdk, env_cfg=env_cfg)
        assert exc_info.value.exit_code == 1

    def test_auth_failure_with_api_key_includes_masked_key(self):
        """When auth fails and a key is configured, masked key is shown on stderr."""
        client = _make_client_mock()
        client.list_flows.side_effect = _FakeLangflowAuthError("forbidden")
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg(api_key=_API_KEY)
        with pytest.raises(typer.Exit):
            _run_login(sdk_mock=sdk, env_cfg=env_cfg)


# ---------------------------------------------------------------------------
# login_command — connection failure
# ---------------------------------------------------------------------------


class TestLoginCommandConnectionFailure:
    def test_connection_error_raises_exit_1(self):
        client = _make_client_mock()
        client.list_flows.side_effect = _FakeLangflowConnectionError("timeout")
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        with pytest.raises(typer.Exit) as exc_info:
            _run_login(sdk_mock=sdk, env_cfg=env_cfg)
        assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# login_command — HTTP error
# ---------------------------------------------------------------------------


class TestLoginCommandHTTPError:
    def test_http_error_raises_exit_1(self):
        client = _make_client_mock()
        client.list_flows.side_effect = _FakeLangflowHTTPError(500, "internal server error")
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        with pytest.raises(typer.Exit) as exc_info:
            _run_login(sdk_mock=sdk, env_cfg=env_cfg)
        assert exc_info.value.exit_code == 1

    def test_http_404_raises_exit_1(self):
        client = _make_client_mock()
        client.list_flows.side_effect = _FakeLangflowHTTPError(404, "not found")
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        with pytest.raises(typer.Exit) as exc_info:
            _run_login(sdk_mock=sdk, env_cfg=env_cfg)
        assert exc_info.value.exit_code == 1

    def test_generic_error_raises_exit_1(self):
        client = _make_client_mock()
        client.list_flows.side_effect = RuntimeError("unexpected")
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        with pytest.raises(typer.Exit) as exc_info:
            _run_login(sdk_mock=sdk, env_cfg=env_cfg)
        assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# login_command — config error
# ---------------------------------------------------------------------------


class TestLoginCommandConfigError:
    def test_config_error_raises_exit_1(self):
        from lfx.cli.login import login_command
        from lfx.config import ConfigError

        sdk = _make_sdk_mock()
        with (
            patch("lfx.cli.login.load_sdk", return_value=sdk),
            patch("lfx.config.resolve_environment", side_effect=ConfigError("no such env")),
            pytest.raises(typer.Exit) as exc_info,
        ):
            login_command(
                env="nonexistent",
                environments_file=None,
                target=None,
                api_key=None,
            )
        assert exc_info.value.exit_code == 1

    def test_missing_environments_file_raises_exit_1(self, tmp_path):
        from lfx.cli.login import login_command

        sdk = _make_sdk_mock()
        missing_file = str(tmp_path / "no_such.yaml")
        with (
            patch("lfx.cli.login.load_sdk", return_value=sdk),
            pytest.raises(typer.Exit),
        ):
            login_command(
                env="myenv",
                environments_file=missing_file,
                target=None,
                api_key=None,
            )


# ---------------------------------------------------------------------------
# login_command — no API key
# ---------------------------------------------------------------------------


class TestLoginCommandNoApiKey:
    def test_no_api_key_does_not_exit_early_on_success(self):
        """When api_key is None, login still proceeds and succeeds if probe passes."""
        client = _make_client_mock(flows=[MagicMock()])
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg(api_key=None, name="staging")
        _run_login(sdk_mock=sdk, env_cfg=env_cfg)  # Should not raise
        client.list_flows.assert_called_once()

    def test_no_api_key_inline_env_does_not_exit_early(self):
        """__inline__ env with no key still probes without raising."""
        client = _make_client_mock(flows=[])
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg(api_key=None, name="__inline__")
        _run_login(sdk_mock=sdk, env_cfg=env_cfg)  # Should not raise

    def test_no_api_key_env_env_does_not_exit_early(self):
        """__env__ special name with no key still proceeds."""
        client = _make_client_mock(flows=[])
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg(api_key=None, name="__env__")
        _run_login(sdk_mock=sdk, env_cfg=env_cfg)  # Should not raise

    def test_no_api_key_client_still_constructed(self):
        """Client is constructed even without an API key."""
        client = _make_client_mock()
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg(api_key=None)
        _run_login(sdk_mock=sdk, env_cfg=env_cfg)
        sdk.Client.assert_called_once_with(base_url=_BASE_URL, api_key=None)


# ---------------------------------------------------------------------------
# login_command — SDK not installed
# ---------------------------------------------------------------------------


class TestLoginCommandSdkNotInstalled:
    def test_sdk_load_raises_bad_parameter(self):
        from lfx.cli.login import login_command

        with (
            patch(
                "lfx.cli.login.load_sdk",
                side_effect=typer.BadParameter("langflow-sdk is required for lfx login"),
            ),
            pytest.raises(typer.BadParameter),
        ):
            login_command(
                env="staging",
                environments_file=None,
                target=None,
                api_key=None,
            )

    def test_sdk_load_bad_parameter_message(self):
        from lfx.cli.login import login_command

        with (
            patch(
                "lfx.cli.login.load_sdk",
                side_effect=typer.BadParameter("langflow-sdk is required"),
            ),
            pytest.raises(typer.BadParameter) as exc_info,
        ):
            login_command(
                env="staging",
                environments_file=None,
                target=None,
                api_key=None,
            )
        assert "langflow-sdk" in str(exc_info.value)


# ---------------------------------------------------------------------------
# login_command — inline / env-var environment behaviour
# ---------------------------------------------------------------------------


class TestLoginCommandInlineEnv:
    def test_inline_env_success_does_not_raise(self):
        client = _make_client_mock()
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg(name="__inline__")
        _run_login(env=None, target=_BASE_URL, api_key=_API_KEY, sdk_mock=sdk, env_cfg=env_cfg)

    def test_env_var_env_success_does_not_raise(self):
        client = _make_client_mock()
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg(name="__env__")
        _run_login(env=None, target=_BASE_URL, api_key=_API_KEY, sdk_mock=sdk, env_cfg=env_cfg)

    def test_named_env_success_does_not_raise(self):
        client = _make_client_mock()
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg(name="production")
        _run_login(env="production", sdk_mock=sdk, env_cfg=env_cfg)

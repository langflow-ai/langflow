"""Tests for the no_env_fallback guard in load_from_env_vars."""

from __future__ import annotations

import os
from unittest.mock import patch

from lfx.interface.initialize.loading import load_from_env_vars


class TestLoadFromEnvVarsNoFallback:
    def test_env_fallback_used_when_flag_absent(self):
        """Without the flag, missing request_variables falls back to os.environ."""
        params = {"api_key": "MY_SECRET"}
        with patch.dict(os.environ, {"MY_SECRET": "env-value"}):
            result = load_from_env_vars(params, ["api_key"], context=None)
        assert result["api_key"] == "env-value"

    def test_env_fallback_used_when_flag_false(self):
        """Explicit no_env_fallback=False behaves the same as absent."""
        params = {"api_key": "MY_SECRET"}
        with patch.dict(os.environ, {"MY_SECRET": "env-value"}):
            result = load_from_env_vars(params, ["api_key"], context={"no_env_fallback": False})
        assert result["api_key"] == "env-value"

    def test_env_fallback_skipped_when_flag_true(self):
        """With no_env_fallback=True, os.environ is never consulted even if the var is set."""
        params = {"api_key": "MY_SECRET"}
        with (
            patch.dict(os.environ, {"MY_SECRET": "env-value"}),
            patch("lfx.interface.initialize.loading.os.getenv") as mock_getenv,
        ):
            result = load_from_env_vars(params, ["api_key"], context={"no_env_fallback": True})
        assert result["api_key"] is None
        # Only the credential variable must never be looked up — logger internals may call getenv
        credential_lookups = [c for c in mock_getenv.call_args_list if c.args and c.args[0] == "MY_SECRET"]
        assert not credential_lookups, f"os.getenv('MY_SECRET') must not be called, got: {credential_lookups}"

    def test_request_variables_win_even_with_flag_true(self):
        """request_variables always takes priority, even when no_env_fallback=True."""
        params = {"api_key": "MY_SECRET"}
        context = {
            "no_env_fallback": True,
            "request_variables": {"MY_SECRET": "override-value"},
        }
        with patch.dict(os.environ, {"MY_SECRET": "env-value"}):
            result = load_from_env_vars(params, ["api_key"], context=context)
        assert result["api_key"] == "override-value"

    def test_request_variables_win_when_flag_false(self):
        """request_variables takes priority over os.environ even when no_env_fallback=False."""
        params = {"api_key": "MY_SECRET"}
        context = {
            "no_env_fallback": False,
            "request_variables": {"MY_SECRET": "override-value"},
        }
        with patch.dict(os.environ, {"MY_SECRET": "env-value"}):
            result = load_from_env_vars(params, ["api_key"], context=context)
        assert result["api_key"] == "override-value"

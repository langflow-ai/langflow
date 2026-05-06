"""Tests for ollama_binary — detects the Ollama CLI binary across all 4 platforms.

Threat model covered:
  - shutil.which alone is fooled by a fake binary in PATH; we corroborate with a real
    --version subprocess to confirm it is the actual Ollama CLI.
  - subprocess MUST never use shell=True and MUST always have a timeout, or a hung /
    malicious binary takes the whole detect path down with it.
  - On Windows the binary is `ollama.exe`; shutil.which handles this transparently
    but the test pins the behavior explicitly.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# is_ollama_installed() — happy path & failure modes
# ---------------------------------------------------------------------------


class TestIsOllamaInstalled:
    def test_should_return_true_when_which_finds_and_version_succeeds(self):
        from lfx.services.local_model import ollama_binary

        completed = MagicMock(returncode=0, stdout="ollama version 0.5.7\n", stderr="")
        with (
            patch("lfx.services.local_model.ollama_binary.shutil.which", return_value="/usr/local/bin/ollama"),
            patch("lfx.services.local_model.ollama_binary.subprocess.run", return_value=completed) as mock_run,
        ):
            assert ollama_binary.is_ollama_installed() is True

        # Adversarial: subprocess.run MUST be called with list args (no shell=True),
        # MUST pass a timeout, and MUST capture output to avoid leaking to stderr.
        call_args = mock_run.call_args
        assert isinstance(call_args.args[0], list), "subprocess.run must use list args, not a shell string"
        assert call_args.kwargs.get("shell") is not True
        assert "timeout" in call_args.kwargs
        assert call_args.kwargs["timeout"] <= 5.0

    def test_should_return_false_when_which_returns_none(self):
        from lfx.services.local_model import ollama_binary

        with patch("lfx.services.local_model.ollama_binary.shutil.which", return_value=None):
            assert ollama_binary.is_ollama_installed() is False

    def test_should_return_false_when_version_returncode_is_nonzero(self):
        # Why: a fake binary with the right name but broken behavior (returncode != 0)
        # is treated as not-installed. Otherwise an attacker dropping a no-op `ollama`
        # in $PATH could trick us into skipping the install path.
        from lfx.services.local_model import ollama_binary

        completed = MagicMock(returncode=127, stdout="", stderr="not found")
        with (
            patch("lfx.services.local_model.ollama_binary.shutil.which", return_value="/usr/local/bin/ollama"),
            patch("lfx.services.local_model.ollama_binary.subprocess.run", return_value=completed),
        ):
            assert ollama_binary.is_ollama_installed() is False

    def test_should_return_false_when_subprocess_times_out(self):
        # Why: a hung binary must not block the whole startup path. TimeoutExpired
        # is treated as "not installed" rather than propagated.
        from lfx.services.local_model import ollama_binary

        with (
            patch("lfx.services.local_model.ollama_binary.shutil.which", return_value="/usr/local/bin/ollama"),
            patch(
                "lfx.services.local_model.ollama_binary.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="ollama", timeout=2),
            ),
        ):
            assert ollama_binary.is_ollama_installed() is False

    def test_should_return_false_when_subprocess_raises_oserror(self):
        # Why: PermissionError, FileNotFoundError (race after which() returned), etc.
        # All map to "not installed" rather than crashing.
        from lfx.services.local_model import ollama_binary

        with (
            patch("lfx.services.local_model.ollama_binary.shutil.which", return_value="/usr/local/bin/ollama"),
            patch("lfx.services.local_model.ollama_binary.subprocess.run", side_effect=PermissionError("denied")),
        ):
            assert ollama_binary.is_ollama_installed() is False


# ---------------------------------------------------------------------------
# ollama_binary_path() — returns Path or None, never raises
# ---------------------------------------------------------------------------


class TestOllamaBinaryPath:
    def test_should_return_path_when_which_finds_binary(self):
        from pathlib import Path

        from lfx.services.local_model import ollama_binary

        with patch("lfx.services.local_model.ollama_binary.shutil.which", return_value="/usr/local/bin/ollama"):
            result = ollama_binary.ollama_binary_path()

        assert result == Path("/usr/local/bin/ollama")

    def test_should_return_none_when_which_returns_none(self):
        from lfx.services.local_model import ollama_binary

        with patch("lfx.services.local_model.ollama_binary.shutil.which", return_value=None):
            assert ollama_binary.ollama_binary_path() is None

    def test_should_handle_windows_exe_suffix(self):
        # Why: shutil.which on Windows respects PATHEXT and returns the .exe path;
        # we don't massage the string ourselves — we just trust shutil.which.
        from pathlib import Path

        from lfx.services.local_model import ollama_binary

        windows_path = "C:\\Users\\dev\\AppData\\Local\\Programs\\Ollama\\ollama.exe"
        with patch("lfx.services.local_model.ollama_binary.shutil.which", return_value=windows_path):
            result = ollama_binary.ollama_binary_path()

        assert result == Path(windows_path)


# ---------------------------------------------------------------------------
# Adversarial — argument injection
# ---------------------------------------------------------------------------


class TestNoArgumentInjection:
    def test_subprocess_args_should_be_a_fixed_list_not_user_controlled(self):
        # Why: the call MUST be a fixed list like ["ollama", "--version"]. If anyone
        # ever refactors this to accept a user-supplied path string and uses shell=True
        # or string-builds the command, command injection becomes possible.
        # This test pins the contract.
        from lfx.services.local_model import ollama_binary

        completed = MagicMock(returncode=0, stdout="ollama version 0.5.7\n", stderr="")
        with (
            patch("lfx.services.local_model.ollama_binary.shutil.which", return_value="/usr/local/bin/ollama"),
            patch("lfx.services.local_model.ollama_binary.subprocess.run", return_value=completed) as mock_run,
        ):
            ollama_binary.is_ollama_installed()

        cmd = mock_run.call_args.args[0]
        assert isinstance(cmd, list)
        assert all(isinstance(part, str) for part in cmd)
        # No shell metacharacters in any arg
        for part in cmd:
            for bad in (";", "&&", "|", "$(", "`", "\n", "\r"):
                assert bad not in part, f"shell metacharacter {bad!r} in subprocess arg {part!r}"

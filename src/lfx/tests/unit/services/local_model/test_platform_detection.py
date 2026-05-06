"""Tests for platform_detection — answers "what platform am I on?" cross-OS.

Threat model covered:
  - False positives in Docker detection cause us to skip auto-install on host machines
    that look like containers (CI runners) — we use multiple signals to reduce risk.
  - False negatives (real Docker not detected) make us try to install Ollama inside
    a container without privileges — also bad. So both paths are explicitly tested.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# system_name() — OS detection
# ---------------------------------------------------------------------------


class TestSystemName:
    @pytest.mark.parametrize(
        ("platform_value", "expected"),
        [
            ("Windows", "windows"),
            ("Darwin", "macos"),
            ("Linux", "linux"),
        ],
    )
    def test_should_return_canonical_name_for_known_platform(self, platform_value, expected):
        from lfx.services.local_model.platform_detection import system_name

        with patch("lfx.services.local_model.platform_detection.platform.system", return_value=platform_value):
            assert system_name() == expected

    def test_should_return_unknown_for_uncommon_platform(self):
        # Why explicit "unknown" sentinel instead of raising: callers branch on this
        # to decide install strategy. A raise here would force every caller to wrap
        # in try/except and the failure mode would be "Langflow refuses to start".
        from lfx.services.local_model.platform_detection import system_name

        with patch("lfx.services.local_model.platform_detection.platform.system", return_value="FreeBSD"):
            assert system_name() == "unknown"


# ---------------------------------------------------------------------------
# is_docker() — container detection
# ---------------------------------------------------------------------------


class TestIsDocker:
    def test_should_return_true_when_dockerenv_file_exists(self):
        # Why /.dockerenv: created by the Docker daemon at container init; it is the
        # canonical signal recommended by the Moby project. Cheap (one stat call).
        from lfx.services.local_model import platform_detection

        with patch.object(Path, "exists", return_value=True), patch.dict("os.environ", {}, clear=True):
            assert platform_detection.is_docker() is True

    def test_should_return_true_when_kubernetes_env_var_set(self):
        # Why: Kubernetes containers do not always have /.dockerenv (e.g., containerd
        # runtime), but the kubelet always injects KUBERNETES_SERVICE_HOST.
        from lfx.services.local_model import platform_detection

        with (
            patch.object(Path, "exists", return_value=False),
            patch.dict("os.environ", {"KUBERNETES_SERVICE_HOST": "10.0.0.1"}, clear=True),
        ):
            assert platform_detection.is_docker() is True

    def test_should_return_false_when_no_signals_present(self):
        from lfx.services.local_model import platform_detection

        with patch.object(Path, "exists", return_value=False), patch.dict("os.environ", {}, clear=True):
            assert platform_detection.is_docker() is False

    def test_should_be_cheap_to_call_repeatedly(self):
        # Why: this gets called on every health check / install decision. Must not
        # do heavy work (no subprocess, no /proc parsing > 1 file). Test is a smoke
        # check that calling it 100x in a row doesn't raise.
        from lfx.services.local_model import platform_detection

        with patch.object(Path, "exists", return_value=False), patch.dict("os.environ", {}, clear=True):
            for _ in range(100):
                platform_detection.is_docker()


# ---------------------------------------------------------------------------
# Module surface — only platform/env detection, no I/O beyond fs/env reads
# ---------------------------------------------------------------------------


class TestModuleSurface:
    def test_module_should_not_import_subprocess(self):
        # Why: this module is the foundational layer. It must NOT shell out — that's
        # ollama_binary's job. Forbidding subprocess at import time keeps the
        # responsibility boundary clean (helper layer rule, no side effects beyond
        # cheap fs/env reads).
        import lfx.services.local_model.platform_detection as mod

        assert "subprocess" not in dir(mod), "platform_detection must not import subprocess"

"""Verify the Makefile exposes a real_services_tests target wired to -m real_services."""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[5]
_MAKEFILE = _REPO_ROOT / "Makefile"


@pytest.mark.no_blockbuster
def test_makefile_has_real_services_target() -> None:
    assert _MAKEFILE.exists(), f"Makefile not found at {_MAKEFILE}"
    text = _MAKEFILE.read_text(encoding="utf-8")
    assert "real_services_tests:" in text, "missing real_services_tests make target"
    target_block = text.split("real_services_tests:", 1)[1].split("\n\n", 1)[0]
    assert "-m real_services" in target_block, "real_services_tests target must select the real_services marker"
    assert "src/backend/tests/unit" in target_block, "target must run the backend unit tree"

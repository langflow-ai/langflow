"""Verify the Makefile exposes a hard_proof_tests target wired to -m hard_proof."""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[5]
_MAKEFILE = _REPO_ROOT / "Makefile"


@pytest.mark.no_blockbuster
def test_makefile_has_hard_proof_target() -> None:
    assert _MAKEFILE.exists(), f"Makefile not found at {_MAKEFILE}"
    text = _MAKEFILE.read_text(encoding="utf-8")
    assert "hard_proof_tests:" in text, "missing hard_proof_tests make target"
    target_block = text.split("hard_proof_tests:", 1)[1].split("\n\n", 1)[0]
    assert "-m hard_proof" in target_block, "hard_proof_tests target must select the hard_proof marker"
    assert "src/backend/tests/unit" in target_block, "target must run the backend unit tree"

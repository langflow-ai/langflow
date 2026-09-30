"""Tests for the LANGFLOW_COMPONENTS_PATH pathsep-split behavior in settings.

The extension loader requires that ``LANGFLOW_COMPONENTS_PATH=/path/A:/path/B``
is parsed as two component paths rather than treated as one literal
non-existent path.  This test exercises the validator directly so it works
without spinning up the full settings service.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from lfx.constants import BASE_COMPONENTS_PATH
from lfx.services.settings.base import Settings

if TYPE_CHECKING:
    from pathlib import Path


def test_pathsep_separated_paths_are_split(monkeypatch, tmp_path: Path) -> None:
    """Two-entry env var produces two components-path entries."""
    path_a = tmp_path / "a"
    path_b = tmp_path / "b"
    path_a.mkdir()
    path_b.mkdir()
    env = f"{path_a}{os.pathsep}{path_b}"
    monkeypatch.setenv("LANGFLOW_COMPONENTS_PATH", env)

    result = Settings.set_components_path([])
    assert str(path_a) in result
    assert str(path_b) in result


def test_walk_order_matches_user_declared_order(monkeypatch, tmp_path: Path) -> None:
    """User-declared path order is preserved across the pathsep split."""
    path_a = tmp_path / "first"
    path_b = tmp_path / "second"
    path_a.mkdir()
    path_b.mkdir()
    monkeypatch.setenv("LANGFLOW_COMPONENTS_PATH", f"{path_a}{os.pathsep}{path_b}")

    result = Settings.set_components_path([])
    # The base components path is appended only when value would be empty,
    # so with explicit env paths the order under test is exactly user order.
    indices = [result.index(str(path_a)), result.index(str(path_b))]
    assert indices == sorted(indices)


def test_non_existent_segments_are_skipped(monkeypatch, tmp_path: Path) -> None:
    """Pathsep entries that don't exist on disk are silently skipped."""
    real = tmp_path / "real"
    real.mkdir()
    bogus = tmp_path / "does-not-exist"
    monkeypatch.setenv("LANGFLOW_COMPONENTS_PATH", f"{real}{os.pathsep}{bogus}")

    result = Settings.set_components_path([])
    assert str(real) in result
    assert str(bogus) not in result


def test_empty_segments_are_ignored(monkeypatch, tmp_path: Path) -> None:
    """Trailing pathsep producing an empty segment doesn't crash."""
    real = tmp_path / "real"
    real.mkdir()
    monkeypatch.setenv("LANGFLOW_COMPONENTS_PATH", f"{real}{os.pathsep}")

    result = Settings.set_components_path([])
    assert str(real) in result


def test_unset_env_falls_back_to_base(monkeypatch) -> None:
    """No env var -> the base components path is the only entry."""
    monkeypatch.delenv("LANGFLOW_COMPONENTS_PATH", raising=False)
    result = Settings.set_components_path([])
    assert result == [BASE_COMPONENTS_PATH]

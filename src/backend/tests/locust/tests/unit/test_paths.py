"""Unit tests for out-of-repo performance-suite artifact paths."""

from __future__ import annotations

from pathlib import Path

from tests.locust.langflow_runtime.paths import corpus_dir, perf_data_root, reports_dir, state_path_for


def test_perf_data_root_honors_perf_data_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PERF_DATA_DIR", str(tmp_path / "suite"))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    root = perf_data_root()
    assert root == (tmp_path / "suite").resolve()
    assert reports_dir() == root / "reports"
    assert state_path_for("perf-local") == root / "state" / "perf-local.json"
    assert corpus_dir("perf-local") == root / "corpus" / "perf-local"


def test_perf_data_root_uses_xdg_cache(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("PERF_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert perf_data_root() == (tmp_path / "xdg" / "langflow-perf").resolve()

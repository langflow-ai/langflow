"""The ops bench keeps its one gc_startup record through a reset. No database, no server."""

from __future__ import annotations

from langflow.services.flow_multiplayer import bench


def test_reset_keeps_gc_startup(monkeypatch):
    startup = {"kind": "gc_startup", "freeze_count": 0, "gen2_objects": 1}
    monkeypatch.setattr(bench, "_gc_startup", startup)
    monkeypatch.setattr(bench, "_records", [startup, {"kind": "req"}, {"kind": "gc", "gen": 2}])
    bench.reset()
    assert bench._records == [startup]
    bench.reset()
    assert bench._records == [startup]

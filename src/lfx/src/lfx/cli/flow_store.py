"""Flow persistence backends for lfx serve.

Three deployment modes — all use the same code path:

- ``NullFlowStore`` (default): in-memory only, no disk writes.
- ``FilesystemFlowStore(directory)``: writes each flow as ``{id}.json``.
  Point at ``/tmp/lfx-flows`` for single-pod sharing across uvicorn workers,
  or at a PVC mount path for cross-pod sharing.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class FlowStore(Protocol):
    """Persistence backend for flow JSON.

    Implementations must be safe to call from multiple OS processes sharing
    the same filesystem (i.e. all writes must be atomic).
    """

    def write(self, flow_id: str, flow_json: dict) -> None:
        """Persist *flow_json* under *flow_id*. Overwrites if already present."""
        ...

    def read(self, flow_id: str) -> dict | None:
        """Return the stored JSON dict for *flow_id*, or ``None`` if absent."""
        ...

    def delete(self, flow_id: str) -> bool:
        """Remove *flow_id* from the store. Returns True if it existed."""
        ...

    def list_ids(self) -> list[str]:
        """Return all stored flow IDs."""
        ...


class NullFlowStore:
    """No-op store — flows live in worker memory only (default)."""

    def write(self, _flow_id: str, _flow_json: dict) -> None:
        pass

    def read(self, _flow_id: str) -> dict | None:
        return None

    def delete(self, _flow_id: str) -> bool:
        return False

    def list_ids(self) -> list[str]:
        return []


class FilesystemFlowStore:
    """Filesystem-backed store.

    Each flow is persisted as ``{directory}/{flow_id}.json``.  Writes are
    atomic (write-to-tmp then replace) so concurrent readers in other workers
    never see a partial file.

    Use ``/tmp/lfx-flows`` for single-pod worker sharing or a PVC mount path
    for cross-pod sharing — the implementation is identical either way.
    """

    def __init__(self, directory: Path) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, flow_id: str) -> Path:
        """Return the path for *flow_id*, raising ValueError for unsafe IDs."""
        if "/" in flow_id or "\\" in flow_id or flow_id.startswith("."):
            msg = f"Invalid flow_id: {flow_id!r}"
            raise ValueError(msg)
        path = self._dir / f"{flow_id}.json"
        try:
            path.resolve().relative_to(self._dir.resolve())
        except ValueError as exc:
            msg = f"Invalid flow_id: {flow_id!r}"
            raise ValueError(msg) from exc
        return path

    def write(self, flow_id: str, flow_json: dict) -> None:
        target = self._safe_path(flow_id)
        tmp = self._dir / f"{flow_id}.{uuid.uuid4().hex}.tmp"
        tmp.write_text(json.dumps(flow_json), encoding="utf-8")
        tmp.replace(target)

    def read(self, flow_id: str) -> dict | None:
        path = self._safe_path(flow_id)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def delete(self, flow_id: str) -> bool:
        path = self._safe_path(flow_id)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        else:
            return True

    def list_ids(self) -> list[str]:
        return [p.stem for p in self._dir.glob("*.json")]

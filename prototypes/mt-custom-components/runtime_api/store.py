"""In-memory tenant-scoped store. Replaces what Langflow services hit in the DB."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
from typing import Any


class Store:
    def __init__(self) -> None:
        self._lock = Lock()
        self._variables: dict[tuple[str, str], str] = {}
        self._memory: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        self._artifacts: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        self._events: list[dict[str, Any]] = []

    def seed_variable(self, tenant_id: str, name: str, value: str) -> None:
        with self._lock:
            self._variables[(tenant_id, name)] = value

    def get_variable(self, tenant_id: str, name: str) -> str | None:
        with self._lock:
            return self._variables.get((tenant_id, name))

    def read_memory(self, tenant_id: str, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._memory[(tenant_id, session_id)])

    def write_memory(self, tenant_id: str, session_id: str, entry: dict[str, Any]) -> None:
        with self._lock:
            self._memory[(tenant_id, session_id)].append(entry)

    def write_artifact(self, tenant_id: str, run_id: str, artifact: dict[str, Any]) -> None:
        with self._lock:
            self._artifacts[(tenant_id, run_id)].append(artifact)

    def read_artifacts(self, tenant_id: str, run_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._artifacts[(tenant_id, run_id)])

    def write_event(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._events.append(event)

    def read_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)


store = Store()

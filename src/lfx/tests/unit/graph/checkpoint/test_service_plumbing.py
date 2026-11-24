"""CHECKPOINT_SERVICE plumbing + lfx-standalone boundary (LE-1440)."""

from __future__ import annotations

import re
from pathlib import Path

import lfx.graph.checkpoint.builder
import lfx.graph.checkpoint.probe
import lfx.graph.checkpoint.resume
import lfx.graph.checkpoint.schema
import lfx.graph.checkpoint.store
import lfx.graph.exceptions
from lfx.graph.checkpoint.store import InMemoryCheckpointStore
from lfx.services.deps import get_checkpoint_service
from lfx.services.schema import ServiceType

_CHECKPOINT_MODULES = (
    lfx.graph.checkpoint.schema,
    lfx.graph.checkpoint.store,
    lfx.graph.checkpoint.builder,
    lfx.graph.checkpoint.resume,
    lfx.graph.checkpoint.probe,
    lfx.graph.exceptions,
)


def test_checkpoint_service_type_registered():
    assert ServiceType.CHECKPOINT_SERVICE == "checkpoint_service"


def test_get_checkpoint_service_falls_back_to_in_memory_singleton():
    first = get_checkpoint_service()
    second = get_checkpoint_service()
    assert isinstance(first, InMemoryCheckpointStore)
    assert first is second


def test_checkpoint_modules_never_import_langflow():
    pattern = re.compile(r"^\s*(from|import)\s+langflow", re.MULTILINE)
    for module in _CHECKPOINT_MODULES:
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert not pattern.search(source), f"{module.__name__} imports langflow — lfx must stay standalone"

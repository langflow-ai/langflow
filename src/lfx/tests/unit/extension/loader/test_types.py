"""Tests for the loader's public dataclasses.

``LoadedComponent`` and ``LoadResult`` are the values the rest of the
Langflow stack consumes (events pipeline, registry, future reload).
These tests pin their shape and behavior independently of the orchestrator
so a future refactor can move the dataclass code without breaking
downstream consumers.

Also covers the loader-specific error-code registration invariant: every
loader code that the orchestrator can emit must be in ``ERROR_CODES``.
"""

from __future__ import annotations

from pathlib import Path

from lfx.extension import (
    SLOT_OFFICIAL,
    LoadedComponent,
    LoadResult,
)
from lfx.extension.errors import ERROR_CODES

# Loader-specific codes the orchestrator / inline-bundle path can emit.
# Keep this list in sync with the producer modules; if a code disappears
# from the registry but stays here (or vice versa), the test below fails.
LOADER_CODES = frozenset(
    {
        "module-import-failed",
        "duplicate-component-name",
        "duplicate-inline-bundle",
        "inline-bundle-name-invalid",
    }
)


# ---------------------------------------------------------------------------
# LoadResult shape
# ---------------------------------------------------------------------------


def test_load_result_default_is_ok() -> None:
    result = LoadResult()
    assert result.ok
    assert bool(result) is True
    assert result.components == []


# ---------------------------------------------------------------------------
# LoadedComponent shape
# ---------------------------------------------------------------------------


def test_loaded_component_namespaced_id_format() -> None:
    class Dummy:
        pass

    component = LoadedComponent(
        extension_id="lfx-pilot",
        extension_version="1.2.3",
        bundle="pilot",
        class_name="PilotThing",
        slot=SLOT_OFFICIAL,
        klass=Dummy,
        module_name="_lfx_ext.official.pilot.thing",
        file_path=Path("/tmp/thing.py"),
    )
    assert component.namespaced_id == "ext:pilot:PilotThing@official"


# ---------------------------------------------------------------------------
# Error-code registry parity
# ---------------------------------------------------------------------------


def test_all_loader_error_codes_are_in_registry() -> None:
    missing = LOADER_CODES - ERROR_CODES
    assert not missing, f"Loader code(s) missing from ERROR_CODES: {sorted(missing)}"

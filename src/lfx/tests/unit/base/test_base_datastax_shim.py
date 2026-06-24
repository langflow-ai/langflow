"""Contract tests for the ``lfx.base.datastax`` compatibility shim.

The datastax graduation moved ``lfx.base.datastax`` into the
``lfx-datastax`` distribution (``lfx_datastax.base``).  Saved flows and
starter-project templates embed ``from lfx.base.datastax.astradb_base
import AstraDBBaseComponent`` inside their stored component ``code``
fields, and that source is re-executed verbatim at flow build time --
so the legacy import path must keep resolving whenever the bundle is
installed.
"""

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

import lfx

_SHIM_PATH = Path(lfx.__file__).resolve().parent / "base" / "datastax" / "__init__.py"

_BUNDLE_INSTALLED = importlib.util.find_spec("lfx_datastax") is not None


def test_shim_file_shape() -> None:
    """The shim is a single marker-tagged file with no sibling implementations."""
    source = _SHIM_PATH.read_text(encoding="utf-8")
    first_line = source.splitlines()[0]
    assert first_line == "# lfx-bundles-shim"
    assert 'importlib.import_module("lfx_datastax.base")' in source
    # Narrow except: only a missing bundle is translated; transitive
    # dep failures must re-raise untouched.
    assert 'exc.name == "lfx_datastax"' in source
    siblings = [p for p in _SHIM_PATH.parent.iterdir() if p.name not in {"__init__.py", "__pycache__"}]
    assert not siblings, f"shim dir must contain only __init__.py, found: {siblings}"


@pytest.mark.skipif(not _BUNDLE_INSTALLED, reason="lfx-datastax not installed in this environment")
def test_shim_aliases_to_bundle_base() -> None:
    """``import lfx.base.datastax`` resolves to ``lfx_datastax.base``."""
    for mod in ("lfx.base.datastax", "lfx.base.datastax.astradb_base"):
        sys.modules.pop(mod, None)
    shim = importlib.import_module("lfx.base.datastax")
    real = importlib.import_module("lfx_datastax.base")
    assert shim is real


@pytest.mark.skipif(not _BUNDLE_INSTALLED, reason="lfx-datastax not installed in this environment")
def test_stored_flow_import_path_resolves() -> None:
    """The exact import embedded in saved-flow code fields keeps working."""
    for mod in ("lfx.base.datastax", "lfx.base.datastax.astradb_base"):
        sys.modules.pop(mod, None)
    namespace: dict[str, object] = {}
    exec("from lfx.base.datastax.astradb_base import AstraDBBaseComponent", namespace)  # noqa: S102
    assert namespace["AstraDBBaseComponent"] is not None

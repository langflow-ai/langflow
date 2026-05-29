"""Regression: the IBM bundle must import without ibm-db (``ibm_db_dbi``).

``ibm-db`` ships no linux/aarch64 wheel, so ``lfx-ibm`` has to load on that
arch even though the DB2 vector store cannot run there -- the watsonx
components still can, and the extension loader expects component imports to
degrade gracefully rather than break discovery.

These tests *simulate* the driver's absence (a ``None`` entry in
``sys.modules`` makes ``import ibm_db_dbi`` raise ``ImportError`` -- the same
trick the in-tree missing-package test uses), so they run on every platform,
including the x86_64 CI runners where ibm-db is installed. They guard against
re-introducing a module-level ``import ibm_db_dbi`` in ``db2vs.py``.
"""

import importlib
import sys

import pytest

# Bundle modules whose module-level code must re-run under the simulated
# absence; dropping them from the cache forces a fresh import.
_BUNDLE_MODULES = (
    "lfx_ibm.components.ibm",
    "lfx_ibm.components.ibm.db2vs",
    "lfx_ibm.components.ibm.db2_vector",
)


@pytest.fixture
def without_ibm_db(monkeypatch):
    """Make the ibm-db driver look uninstalled (as on linux/aarch64)."""
    monkeypatch.setitem(sys.modules, "ibm_db", None)
    monkeypatch.setitem(sys.modules, "ibm_db_dbi", None)
    for name in _BUNDLE_MODULES:
        monkeypatch.delitem(sys.modules, name, raising=False)


@pytest.mark.usefixtures("without_ibm_db")
def test_db2vs_module_imports_without_ibm_db():
    """db2vs must import with no module-level ibm_db_dbi dependency."""
    module = importlib.import_module("lfx_ibm.components.ibm.db2vs")
    assert module is not None


@pytest.mark.usefixtures("without_ibm_db")
def test_bundle_components_import_without_ibm_db():
    """The bundle package and all its components import without the driver."""
    from lfx_ibm.components.ibm import (
        DB2VectorStoreComponent,
        WatsonxAIComponent,
        WatsonxEmbeddingsComponent,
    )

    assert DB2VectorStoreComponent is not None
    assert WatsonxAIComponent is not None
    assert WatsonxEmbeddingsComponent is not None


@pytest.mark.usefixtures("without_ibm_db")
def test_db2_vector_store_use_raises_clean_import_error():
    """Using the DB2 vector store without the driver raises a clean ImportError."""
    from lfx_ibm.components.ibm import DB2VectorStoreComponent

    with pytest.raises(ImportError, match="ibm_db"):
        DB2VectorStoreComponent().build_vector_store()

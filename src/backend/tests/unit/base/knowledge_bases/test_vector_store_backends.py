"""Stub-state tests for the disabled DB-connector backends.

The Astra / MongoDB / Postgres backends ship as stubs in this phase
(see each module's docstring under
``lfx.base.knowledge_bases.backends``). These tests pin the
"intentionally disabled" contract so accidental re-registration or
silent re-introduction of partial implementations fails loudly:

* the classes still import (preserves enum + type compatibility),
* the registry does NOT bind them (``create_backend('astra')`` raises),
* directly instantiated stubs raise ``NotImplementedError`` from
  ``_build_vector_store`` instead of half-working.

When a backend is re-enabled, restore its real test module alongside
the implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lfx.base.knowledge_bases.backends import (
    AstraBackend,
    BackendType,
    MongoDBBackend,
    PostgresBackend,
    create_backend,
    registered_backends,
)

if TYPE_CHECKING:
    from pathlib import Path

_STUBBED_BACKENDS = (
    (BackendType.ASTRA, AstraBackend),
    (BackendType.MONGODB, MongoDBBackend),
    (BackendType.POSTGRES, PostgresBackend),
)


class TestStubbedBackendsNotRegistered:
    """Stubbed backends are intentionally absent from ``registered_backends()``."""

    @pytest.mark.parametrize(
        ("backend_type", "_backend_class"),
        _STUBBED_BACKENDS,
        ids=lambda v: v.value if isinstance(v, BackendType) else "cls",
    )
    def test_not_in_registry(self, backend_type, _backend_class):
        assert backend_type not in registered_backends()

    @pytest.mark.parametrize(
        ("backend_type", "_backend_class"),
        _STUBBED_BACKENDS,
        ids=lambda v: v.value if isinstance(v, BackendType) else "cls",
    )
    def test_create_backend_raises(self, backend_type, _backend_class, tmp_path: Path):
        with pytest.raises(ValueError, match="not registered"):
            create_backend(backend_type, kb_name="kb", kb_path=tmp_path)


class TestStubbedBackendDirectInstantiation:
    """Bypassing the registry still surfaces a clear ``NotImplementedError``.

    These guards matter because some legacy call sites historically
    constructed backends directly. With the implementation gutted, the
    stub must fail loudly rather than e.g. silently returning ``None``.
    """

    @pytest.mark.parametrize(
        ("_backend_type", "backend_class"),
        _STUBBED_BACKENDS,
        ids=lambda v: v.value if isinstance(v, BackendType) else v.__name__,
    )
    def test_build_vector_store_raises(self, _backend_type, backend_class, tmp_path: Path):
        backend = backend_class(kb_name="kb", kb_path=tmp_path, backend_config={})
        with pytest.raises(NotImplementedError, match="not available in this build"):
            backend._build_vector_store()

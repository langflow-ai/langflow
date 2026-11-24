"""SQLite selection must not accidentally load the retired provider SDKs."""

import subprocess
import sys
from uuid import uuid4

import pytest
from lfx.base.knowledge_bases.backends import BackendType, create_backend, is_local_backend, registered_backends


def test_registry_and_sqlite_import_without_chroma():
    # A new interpreter avoids conftest's application imports and cached SDKs.
    # A forbidden import raises even when the test environment has Chroma.
    result = subprocess.run(  # noqa: S603 - fixed Python snippet in a fresh test interpreter
        [
            sys.executable,
            "-c",
            """
import importlib.abc
import sys
class RejectChroma(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'chromadb', 'langchain_chroma'}:
            raise AssertionError('Forbidden provider import: ' + fullname)
sys.meta_path.insert(0, RejectChroma())
from lfx.base.knowledge_bases.backends import SQLiteBackend, registered_backends
assert 'sqlite' in registered_backends()
assert SQLiteBackend.backend_type == 'sqlite'
""",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("backend", "config", "expected"),
    [
        ("sqlite", {}, True),
        ("chroma", {}, True),
        ("chroma", {"mode": "cloud"}, False),
        (None, {}, True),
        ("postgres", {}, False),
        ("opensearch", {}, False),
    ],
)
def test_local_storage_capability(backend, config, expected):
    assert is_local_backend(backend, config) is expected


def test_unknown_backend_is_not_assumed_remote():
    with pytest.raises(ValueError, match="Unknown vector-store backend"):
        is_local_backend("unknown", {})


def test_sqlite_requires_explicit_storage_identity():
    assert BackendType.SQLITE in registered_backends()
    with pytest.raises(ValueError, match="trusted owner"):
        create_backend("sqlite", "display name")


def test_factory_preserves_trusted_storage_context(tmp_path):
    from lfx.base.knowledge_bases.backends import SQLiteBackend, SQLiteStorageContext

    context = SQLiteStorageContext(root=tmp_path, owner_id=uuid4(), kb_id=uuid4(), generation=1)
    backend = create_backend("sqlite", "display name", storage_context=context)
    assert isinstance(backend, SQLiteBackend)
    # Construction alone must not create a missing database or root.
    assert not list(tmp_path.iterdir())


def test_local_context_is_not_accepted_for_remote_provider(tmp_path):
    from lfx.base.knowledge_bases.backends import SQLiteStorageContext

    context = SQLiteStorageContext(root=tmp_path, owner_id=uuid4(), kb_id=uuid4(), generation=1)
    with pytest.raises(ValueError, match="only by SQLite"):
        create_backend("postgres", "kb", storage_context=context)

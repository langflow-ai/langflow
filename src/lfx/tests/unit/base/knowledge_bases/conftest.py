"""Stand-ins for the optional packages the KB backend package imports.

``lfx.base.knowledge_bases.backends`` registers Chroma on package import, so
reaching *any* backend module — ``postgres.py`` included — pulls in ``chromadb``
and ``langchain_chroma``. Neither is a runtime dependency of lfx (they arrive
with the full ``langflow`` distribution), and neither is installed in the lfx
test environment; the same is true of ``pgvector``.

Rather than pull three heavyweight packages into lfx's dev group purely to reach
``postgres.py``, the absent ones are stood up here. Real installs always win:
each shim registers only when the package is genuinely missing, so a
full-workspace run exercises the real thing.

The ``pgvector`` shim is a real SQLAlchemy ``UserDefinedType`` that renders the
same ``vector(N)`` column spec and the same ``<=>`` cosine-distance operator as
the published client, so the SQL these tests assert on is the SQL production
builds.
"""

from __future__ import annotations

import sys
import types
from importlib.util import find_spec

# Names this conftest actually inserted into ``sys.modules`` (i.e. that weren't
# already present). Tracked so ``pytest_unconfigure`` can remove exactly those
# at session end and the shims don't leak into unrelated suites in the same run.
_INSTALLED_SHIMS: list[str] = []


def _is_missing(module_name: str) -> bool:
    try:
        return find_spec(module_name) is None
    except (ImportError, ValueError):
        return True


def _register(modules: dict[str, types.ModuleType]) -> None:
    # Equivalent to ``setdefault`` (a real install always wins) but records what
    # we inserted so it can be torn down. See ``_INSTALLED_SHIMS``.
    for name, module in modules.items():
        if name not in sys.modules:
            sys.modules[name] = module
            _INSTALLED_SHIMS.append(name)


def _install_chromadb_shim() -> None:
    """Satisfy ``chroma.py``'s module-level imports without the real client.

    Every attribute is import-time surface only; anything that would actually
    talk to Chroma raises, so a test that strays onto the Chroma path fails
    loudly instead of silently passing against a stub.
    """

    class ChromaError(Exception):
        """Stands in for ``chromadb.errors.ChromaError``."""

    class Settings:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class SharedSystemClient:
        _identifier_to_system: dict[str, object] = {}

    class _Unavailable:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            msg = "chromadb is not installed in the lfx test environment."
            raise RuntimeError(msg)

    chromadb = types.ModuleType("chromadb")
    errors = types.ModuleType("chromadb.errors")
    config = types.ModuleType("chromadb.config")
    api = types.ModuleType("chromadb.api")
    shared_system_client = types.ModuleType("chromadb.api.shared_system_client")

    errors.ChromaError = ChromaError
    config.Settings = Settings
    shared_system_client.SharedSystemClient = SharedSystemClient
    api.shared_system_client = shared_system_client
    chromadb.errors = errors
    chromadb.config = config
    chromadb.api = api
    chromadb.PersistentClient = _Unavailable
    chromadb.CloudClient = _Unavailable

    _register(
        {
            "chromadb": chromadb,
            "chromadb.errors": errors,
            "chromadb.config": config,
            "chromadb.api": api,
            "chromadb.api.shared_system_client": shared_system_client,
        }
    )


def _install_langchain_chroma_shim() -> None:
    class Chroma:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            msg = "langchain_chroma is not installed in the lfx test environment."
            raise RuntimeError(msg)

    module = types.ModuleType("langchain_chroma")
    module.Chroma = Chroma
    _register({"langchain_chroma": module})


def _install_pgvector_shim() -> None:
    """Mirror ``pgvector.sqlalchemy.Vector`` closely enough to compile real SQL."""
    from sqlalchemy.types import Float, UserDefinedType

    class Vector(UserDefinedType):
        cache_ok = True

        def __init__(self, dim: int | None = None) -> None:
            self.dim = dim

        def get_col_spec(self, **_kwargs: object) -> str:
            return "VECTOR" if self.dim is None else f"VECTOR({self.dim})"

        def bind_processor(self, dialect):  # noqa: ARG002 — SQLAlchemy hook signature
            def process(value):
                if value is None:
                    return None
                return "[" + ",".join(str(float(v)) for v in value) + "]"

            return process

        class comparator_factory(UserDefinedType.Comparator):  # noqa: N801 — SQLAlchemy hook name
            def cosine_distance(self, other):
                return self.op("<=>", return_type=Float)(other)

    pgvector = types.ModuleType("pgvector")
    sqlalchemy_module = types.ModuleType("pgvector.sqlalchemy")
    sqlalchemy_module.Vector = Vector
    pgvector.sqlalchemy = sqlalchemy_module

    _register({"pgvector": pgvector, "pgvector.sqlalchemy": sqlalchemy_module})


if _is_missing("chromadb"):
    _install_chromadb_shim()
if _is_missing("langchain_chroma"):
    _install_langchain_chroma_shim()
if _is_missing("pgvector"):
    _install_pgvector_shim()


def pytest_unconfigure(config: object) -> None:  # noqa: ARG001 — pytest hook signature
    """Remove the stand-in modules this conftest installed at session end.

    Only pops entries we actually inserted (never a real install), so the shims
    don't outlive this package's session and leak into other suites.
    """
    for name in reversed(_INSTALLED_SHIMS):
        if isinstance(sys.modules.get(name), types.ModuleType) and getattr(sys.modules[name], "__file__", None) is None:
            sys.modules.pop(name, None)
    _INSTALLED_SHIMS.clear()

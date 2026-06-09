"""OpenSearch k-NN vector-store backend.

Wraps ``langchain_community.vectorstores.OpenSearchVectorSearch`` so
Langflow Knowledge Bases can target a self-hosted or managed
OpenSearch cluster (AWS OpenSearch Service, Aiven, OpenSearch
Project, etc.) alongside the other native DB connectors. URL and
auth credentials are resolved through Langflow's ``variable_service``
so ``backend_config`` only carries variable *names* — never raw
secrets — and round-trips cleanly through the UI.

``backend_config`` fields:

* ``url_variable`` — name of the Langflow variable holding the
  cluster URL. Defaults to ``OPENSEARCH_URL``. Required.
* ``username_variable`` — name of the variable holding the basic-auth
  user. Optional; defaults to ``OPENSEARCH_USERNAME``.
* ``password_variable`` — name of the variable holding the basic-auth
  credential. Optional; defaults to the ``OPENSEARCH_PASSWORD``
  variable name. Only the *variable name* lives in config — never
  the raw credential.
* ``index_name`` — OpenSearch index this KB writes / reads. Required.
* ``vector_field`` — document field for the embedding vector.
  Defaults to ``vector_field`` — the field LangChain's
  ``OpenSearchVectorSearch`` actually writes to. That wrapper derives
  ``vector_field`` from *per-call* kwargs (default ``"vector_field"``)
  and ignores the value handed to its constructor, and this backend
  never passes a per-call override — so ingested embeddings always land
  under ``vector_field`` regardless of this setting. ``iter_documents``
  (which powers ``include_embeddings`` retrieval) reads the configured
  field but **falls back to ``vector_field``** so stored vectors come
  back even when a KB's persisted config names a different, never-
  actually-written field (e.g. the legacy ``chunk_embedding`` default).
  Operators pointing the KB at an externally-populated index can still
  set ``vector_field`` to read embeddings from a custom field.
* ``text_field`` — document field for the chunk text. Defaults to
  ``text``.
* ``engine`` — k-NN engine (``jvector``, ``nmslib``, ``faiss``,
  ``lucene``). Defaults to ``jvector``.
* ``space_type`` — distance metric. Defaults to ``l2``.
* ``use_ssl`` / ``verify_certs`` — TLS toggles. Default to ``True``.

Optional dependencies: ``langchain-community`` ships the LangChain
wrapper; ``opensearch-py`` ships the raw client used for count /
stats / scan / delete-by-query. Both are imported lazily so
Langflow installs without OpenSearch deps keep working.
"""

from __future__ import annotations

import asyncio
import queue as sync_queue
import threading
from typing import TYPE_CHECKING, Any

from lfx.base.knowledge_bases.backends.base import (
    BackendType,
    BaseVectorStoreBackend,
    IngestedDocument,
    TestConnectionResult,
    drain_queue_until_sentinel,
)
from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langchain_core.vectorstores import VectorStore


DEFAULT_URL_VARIABLE = "OPENSEARCH_URL"
DEFAULT_USERNAME_VARIABLE = "OPENSEARCH_USERNAME"
DEFAULT_PASSWORD_VARIABLE = "OPENSEARCH_PASSWORD"  # noqa: S105 — variable name, not a secret  # pragma: allowlist secret
# LangChain's ``OpenSearchVectorSearch`` resolves ``vector_field`` from
# per-call kwargs (default ``"vector_field"``) and ignores the value passed to
# its constructor. This backend never passes a per-call override, so ingestion
# writes — and similarity search reads — always land on
# ``LANGCHAIN_DEFAULT_VECTOR_FIELD`` regardless of the configured name.
# ``DEFAULT_VECTOR_FIELD`` is therefore only the *config* fallback used when a
# KB's ``backend_config`` doesn't name one.
DEFAULT_VECTOR_FIELD = "vector_field"
# The field LangChain physically stores embeddings under for this backend (see
# above). ``iter_documents`` reads the configured field but falls back to this
# so ``include_embeddings`` retrieval still returns the stored vectors even when
# a KB's persisted ``backend_config.vector_field`` names a different, never-
# actually-written field — e.g. the historical ``chunk_embedding`` default the
# DB-providers UI still writes.
LANGCHAIN_DEFAULT_VECTOR_FIELD = "vector_field"
DEFAULT_TEXT_FIELD = "text"
# ``faiss`` is part of the core OpenSearch k-NN plugin on every
# released version (1.x → 3.x) and works without extra cluster setup.
# ``jvector`` was tempting (it's faster on OpenSearch 3.2+) but it
# requires the JVector plugin to be explicitly enabled, and rejects
# index creation with ``mapper_parsing_exception: Invalid engine``
# when it isn't — silently failing first-time ingestion. Prefer
# correctness over peak speed for the default; operators chasing
# JVector latency can still set ``engine`` in ``backend_config``.
DEFAULT_ENGINE = "faiss"
DEFAULT_SPACE_TYPE = "l2"


def _coerce_bool(value: Any, *, default: bool) -> bool:
    """Coerce a config value to ``bool`` with explicit string handling.

    The Pydantic ``backend_config: dict[str, Any]`` happily round-trips
    JSON ``true``/``false`` as Python booleans, but rows persisted via
    the variable_service (or older clients) may surface ``"true"`` /
    ``"false"`` as strings. ``bool("false")`` is ``True`` in Python, so
    a naive cast silently flips the toggle. Accept the obvious string
    forms and fall back to ``default`` for anything ambiguous.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return default


class OpenSearchBackend(BaseVectorStoreBackend):
    """OpenSearch k-NN as a Langflow KB backend."""

    backend_type = BackendType.OPENSEARCH

    def _required(self, key: str) -> str:
        value = self.backend_config.get(key)
        if not value:
            msg = f"OpenSearchBackend requires '{key}' in backend_config."
            raise ValueError(msg)
        return str(value)

    async def _resolve_secrets(self) -> None:
        """Resolve URL + optional basic-auth credentials via variable_service.

        The URL is required. Username / password are optional — clusters
        that terminate auth at an upstream proxy or use IAM/sigv4 can
        skip them entirely. When only one of username/password is set
        we log a warning but continue; OpenSearch will surface the real
        auth error at request time with a clearer message than we could
        invent here.
        """
        url_variable = self.backend_config.get("url_variable") or DEFAULT_URL_VARIABLE
        url = await self.resolve_secret(url_variable)
        if not url:
            msg = (
                f"OpenSearchBackend needs the {url_variable!r} Langflow variable "
                "(or env var of the same name) populated with the cluster URL."
            )
            raise ValueError(msg)
        self._resolved_url = url

        username_variable = self.backend_config.get("username_variable") or DEFAULT_USERNAME_VARIABLE
        password_variable = self.backend_config.get("password_variable") or DEFAULT_PASSWORD_VARIABLE
        self._resolved_username = await self.resolve_secret(username_variable)
        self._resolved_password = await self.resolve_secret(password_variable)

    def _build_vector_store(self) -> VectorStore:
        # Validate config before touching optional deps so missing
        # fields surface as a clean ``ValueError`` regardless of
        # whether the OpenSearch extras are installed.
        index_name = self._required("index_name")
        url = getattr(self, "_resolved_url", None)
        if not url:
            msg = "OpenSearchBackend.ensure_ready() must be awaited before _build_vector_store."
            raise RuntimeError(msg)

        vector_field = self.backend_config.get("vector_field") or DEFAULT_VECTOR_FIELD
        text_field = self.backend_config.get("text_field") or DEFAULT_TEXT_FIELD
        engine = self.backend_config.get("engine") or DEFAULT_ENGINE
        space_type = self.backend_config.get("space_type") or DEFAULT_SPACE_TYPE
        # Honor the URL scheme as the SSL default so ``http://localhost:9200``
        # actually talks plain HTTP. opensearch-py treats ``hosts=[url]`` +
        # ``use_ssl=True`` as "force HTTPS" regardless of the URL scheme,
        # which silently rewrites ``http://`` to ``https://`` and fails
        # connection-refused against HTTP-only clusters. Explicit
        # ``use_ssl`` / ``verify_certs`` in backend_config still wins so
        # operators running TLS over an unusual scheme can override.
        scheme = url.split("://", 1)[0].lower() if "://" in url else ""
        scheme_implies_ssl = scheme != "http"
        use_ssl = _coerce_bool(self.backend_config.get("use_ssl"), default=scheme_implies_ssl)
        # ``verify_certs`` is moot when SSL is off; mirror the SSL default
        # rather than blindly enabling cert verification on a plain-HTTP
        # connection (which raises confusing TLS errors).
        verify_certs = _coerce_bool(self.backend_config.get("verify_certs"), default=use_ssl)

        try:
            from langchain_community.vectorstores import OpenSearchVectorSearch
            from opensearchpy import OpenSearch
        except ImportError as exc:
            msg = (
                "OpenSearchBackend requires langchain-community and opensearch-py. "
                "Install the 'opensearch' extras or add those packages."
            )
            raise RuntimeError(msg) from exc

        http_auth: tuple[str, str] | None = None
        if self._resolved_username and self._resolved_password:
            http_auth = (self._resolved_username, self._resolved_password)

        # Stash a raw client for count / stats / scan / delete — the
        # LangChain wrapper exposes these unevenly across versions, and
        # we need a stable surface for ``iter_documents`` + ``count``.
        self._os_client = OpenSearch(
            hosts=[url],
            http_auth=http_auth,
            use_ssl=use_ssl,
            verify_certs=verify_certs,
        )
        self._os_index = index_name
        self._os_vector_field = vector_field
        self._os_text_field = text_field

        return OpenSearchVectorSearch(
            opensearch_url=url,
            index_name=index_name,
            embedding_function=self.embedding_function,
            http_auth=http_auth,
            use_ssl=use_ssl,
            verify_certs=verify_certs,
            vector_field=vector_field,
            text_field=text_field,
            engine=engine,
            space_type=space_type,
        )

    async def similarity_search(
        self,
        query: str,
        k: int,
        *,
        filter: dict[str, Any] | None = None,  # noqa: A002 — matches LangChain VectorStore API
        with_scores: bool = False,
    ) -> list[tuple[Any, float]]:
        """Override the base impl to omit ``filter`` when it's ``None``.

        LangChain's ``OpenSearchVectorSearch`` forwards ``filter=None``
        directly into the k-NN query body as ``"filter": null``, and
        OpenSearch rejects that with::

            x_content_parse_exception:
              [knn] filter doesn't support values of type: VALUE_NULL

        Dropping the kwarg lets the wrapper build the body without the
        key, which is what every Langflow callsite that doesn't pass a
        filter actually wants.
        """
        await self.ensure_ready()
        kwargs: dict[str, Any] = {"query": query, "k": k}
        if filter:
            kwargs["filter"] = filter
        if with_scores:
            return await self.vector_store.asimilarity_search_with_score(**kwargs)
        docs = await self.vector_store.asimilarity_search(**kwargs)
        return [(doc, 0.0) for doc in docs]

    async def count(self) -> int:
        await self.ensure_ready()
        client = getattr(self, "_os_client", None)
        if client is None:
            # Force a build so ``_os_client`` is populated.
            _ = self.vector_store
            client = self._os_client
        try:
            result = await asyncio.to_thread(client.count, index=self._os_index)
            return int(result.get("count") or 0)
        except Exception as exc:  # noqa: BLE001
            # ``warning`` (not ``debug``) so an unreachable cluster /
            # missing index surfaces in default-level server logs and
            # the user can correlate a 0-chunk count with the real cause.
            logger.warning("OpenSearch count() failed for %s: %s", self.kb_name, exc)
            return 0

    async def test_connection(self) -> TestConnectionResult:
        """Validate auth + reachability via ``cluster.info()``.

        The LangChain wrapper builds lazily, so the default
        ``test_connection`` would only catch construction-time mistakes.
        Calling ``cluster.info()`` on the raw ``opensearch-py`` client
        exercises the same auth / SSL / DNS path ingestion uses, but
        without requiring the index to exist yet — operators commonly
        configure the backend before creating the index.
        """
        try:
            await self.ensure_ready()
        except ValueError as exc:
            return TestConnectionResult(
                ok=False,
                message=str(exc),
                details={"type": "ConfigError"},
            )
        except Exception as exc:  # noqa: BLE001
            return TestConnectionResult(
                ok=False,
                message=str(exc) or type(exc).__name__,
                details={"type": type(exc).__name__},
            )

        try:
            _ = self.vector_store  # populates self._os_client
        except Exception as exc:  # noqa: BLE001
            return TestConnectionResult(
                ok=False,
                message=str(exc) or type(exc).__name__,
                details={"type": type(exc).__name__},
            )

        client = getattr(self, "_os_client", None)
        if client is None:  # pragma: no cover — _build_vector_store always sets this
            return TestConnectionResult(
                ok=False,
                message="OpenSearch client was not initialized.",
                details={"type": "RuntimeError"},
            )

        try:
            from opensearchpy.exceptions import (
                AuthenticationException,
                AuthorizationException,
            )
            from opensearchpy.exceptions import (
                ConnectionError as OpenSearchConnectionError,
            )
            from opensearchpy.exceptions import (
                SSLError as OpenSearchSSLError,
            )
        except ImportError as exc:
            return TestConnectionResult(
                ok=False,
                message="opensearch-py is not installed. Install the 'opensearch' extras.",
                details={"type": type(exc).__name__},
            )

        # ``opensearch-py`` exposes ``info()`` on the top-level client
        # (not on ``client.cluster`` — that namespace covers
        # ``health/state/stats`` etc.). Calling ``client.cluster.info``
        # raises ``AttributeError: 'ClusterClient' object has no
        # attribute 'info'`` instead of the connectivity error we want
        # to surface.
        try:
            info = await asyncio.to_thread(client.info)
        except AuthenticationException as exc:
            return TestConnectionResult(
                ok=False,
                message="Authentication failed. Check the username and password variables.",
                details={"type": "AuthenticationException", "error": str(exc)},
            )
        except AuthorizationException as exc:
            return TestConnectionResult(
                ok=False,
                message="Authorization failed. The user is reachable but lacks cluster permissions.",
                details={"type": "AuthorizationException", "error": str(exc)},
            )
        except OpenSearchSSLError as exc:
            return TestConnectionResult(
                ok=False,
                message=(
                    "TLS handshake failed. Verify the URL scheme matches the cluster, and "
                    "toggle 'Verify TLS cert' off if you are using a self-signed certificate."
                ),
                details={"type": "SSLError", "error": str(exc)},
            )
        except OpenSearchConnectionError as exc:
            return TestConnectionResult(
                ok=False,
                message=(
                    "Could not reach the cluster. Verify the URL, network access, and that "
                    "the 'Use TLS' toggle matches the cluster's scheme."
                ),
                details={"type": "ConnectionError", "error": str(exc)},
            )
        except Exception as exc:  # noqa: BLE001
            return TestConnectionResult(
                ok=False,
                message=str(exc) or type(exc).__name__,
                details={"type": type(exc).__name__},
            )

        cluster_name = ""
        version = ""
        if isinstance(info, dict):
            cluster_name = str(info.get("cluster_name") or "")
            version_info = info.get("version")
            if isinstance(version_info, dict):
                version = str(version_info.get("number") or "")
        return TestConnectionResult(
            ok=True,
            message=f"Connected to OpenSearch cluster {cluster_name or '(unnamed)'}".strip(),
            details={"cluster_name": cluster_name, "version": version},
        )

    async def iter_documents(
        self,
        *,
        batch_size: int = 5000,
        include_embeddings: bool = False,
    ) -> AsyncIterator[list[IngestedDocument]]:
        """Stream documents via ``opensearchpy.helpers.scan``.

        OpenSearch's scan cursor ties to a scroll context on the cluster
        side; the helper is a Python generator and is NOT thread-safe
        across workers. We run the entire scan lifetime on *one* worker
        thread and stream batches through a bounded queue, mirroring
        the Mongo / Postgres / Astra pattern.
        """
        await self.ensure_ready()
        client = getattr(self, "_os_client", None)
        if client is None:
            _ = self.vector_store
            client = self._os_client

        try:
            from opensearchpy import helpers as os_helpers
        except ImportError as exc:  # pragma: no cover — build path would have failed already
            msg = "OpenSearchBackend requires opensearch-py. Install the 'opensearch' extras."
            raise RuntimeError(msg) from exc

        index = self._os_index
        vector_field = self._os_vector_field
        text_field = self._os_text_field
        # LangChain stores embeddings under its own default field for this
        # backend (see ``LANGCHAIN_DEFAULT_VECTOR_FIELD``), so the on-disk field
        # is ``vector_field`` regardless of what the KB's persisted config names
        # (historically ``chunk_embedding``). Read the configured field first
        # (honouring an explicit override on an externally-populated index) and
        # fall back to LangChain's field so ``include_embeddings`` retrieval
        # actually returns the stored vectors.
        embedding_fields = [vector_field]
        if LANGCHAIN_DEFAULT_VECTOR_FIELD not in embedding_fields:
            embedding_fields.append(LANGCHAIN_DEFAULT_VECTOR_FIELD)
        # Skip the embedding column(s) in ``_source`` when the caller doesn't
        # need them — large embedding vectors dominate scroll payloads.
        source_excludes = None if include_embeddings else list(embedding_fields)
        # Keys that are never chunk metadata when we have to reconstruct it from
        # a flat ``_source`` (the non-LangChain layout fallback below).
        non_metadata_keys = {text_field, "metadata", *embedding_fields}

        sentinel = object()
        batch_queue: sync_queue.Queue[Any] = sync_queue.Queue(maxsize=2)
        cancel_event = threading.Event()

        def _put_cancelable(item: Any) -> bool:
            while not cancel_event.is_set():
                try:
                    batch_queue.put(item, timeout=0.05)
                except sync_queue.Full:
                    continue
                return True
            return False

        def _stream_batches() -> None:
            scanner = None
            try:
                scanner = os_helpers.scan(
                    client,
                    index=index,
                    size=batch_size,
                    _source_excludes=source_excludes,
                    preserve_order=False,
                )
                buf: list[IngestedDocument] = []
                for hit in scanner:
                    if cancel_event.is_set():
                        break
                    source = hit.get("_source") if isinstance(hit, dict) else {}
                    if not isinstance(source, dict):
                        source = {}
                    content = source.get(text_field) or ""
                    metadata = source.get("metadata")
                    if not isinstance(metadata, dict):
                        metadata = {k: v for k, v in source.items() if k not in non_metadata_keys}
                    embedding: list[float] | None = None
                    if include_embeddings:
                        raw_vec = next(
                            (source[field] for field in embedding_fields if source.get(field) is not None),
                            None,
                        )
                        if raw_vec is not None:
                            embedding = list(raw_vec)
                    buf.append(
                        IngestedDocument(
                            content=str(content),
                            metadata=dict(metadata),
                            embedding=embedding,
                        )
                    )
                    if len(buf) >= batch_size:
                        if not _put_cancelable(buf):
                            buf = []
                            break
                        buf = []
                if buf and not cancel_event.is_set():
                    _put_cancelable(buf)
            except Exception as exc:  # noqa: BLE001
                if not cancel_event.is_set():
                    _put_cancelable(exc)
            finally:
                # ``helpers.scan`` owns the scroll context and closes it
                # on generator cleanup; explicit ``close`` on the
                # generator is the documented way to release it early.
                if scanner is not None:
                    try:
                        scanner.close()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("OpenSearch scan close failed: %s", exc)
                batch_queue.put(sentinel)

        worker = asyncio.create_task(asyncio.to_thread(_stream_batches))
        sentinel_seen = False
        try:
            while True:
                item = await asyncio.to_thread(batch_queue.get)
                if item is sentinel:
                    sentinel_seen = True
                    break
                if isinstance(item, Exception):
                    # Bumped from ``debug`` to ``warning`` so cluster
                    # auth / connection errors surface during ingestion
                    # metric refresh instead of silently truncating the
                    # iterator. Callers that need the exception to
                    # propagate should rely on ``count`` / ``add_documents``
                    # which let it bubble.
                    logger.warning("OpenSearch iter_documents worker failed for %s: %s", self.kb_name, item)
                    await asyncio.to_thread(batch_queue.get)
                    sentinel_seen = True
                    break
                yield item
        finally:
            cancel_event.set()
            if not sentinel_seen:
                await asyncio.to_thread(drain_queue_until_sentinel, batch_queue, sentinel)
            await worker

    async def delete_by(self, where: dict[str, Any]) -> None:
        """Delete documents via ``delete_by_query``.

        ``where`` is translated to a bool-must query. LangChain's
        OpenSearch adapter stores ``Document.metadata`` under the nested
        ``metadata`` source key, while older/manual indexes may expose
        metadata fields at top level, so each key matches either shape.
        """
        await self.ensure_ready()
        client = getattr(self, "_os_client", None)
        if client is None:
            _ = self.vector_store
            client = self._os_client
        if not where:
            return
        must = [
            {
                "bool": {
                    "should": [
                        {"match": {key: value}},
                        {"match": {f"metadata.{key}": value}},
                    ],
                    "minimum_should_match": 1,
                }
            }
            for key, value in where.items()
        ]
        body = {"query": {"bool": {"must": must}}}
        try:
            await asyncio.to_thread(
                client.delete_by_query,
                index=self._os_index,
                body=body,
                refresh=True,
            )
        except Exception as exc:  # noqa: BLE001
            # ``delete_by`` is the rollback path; a silent debug log
            # would let stale chunks linger after a failed ingestion
            # without the operator ever knowing.
            logger.warning("OpenSearch delete_by_query failed for %s: %s", self.kb_name, exc)

    async def storage_size_bytes(self) -> int:
        await self.ensure_ready()
        client = getattr(self, "_os_client", None)
        if client is None:
            return 0
        try:
            stats = await asyncio.to_thread(client.indices.stats, index=self._os_index)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenSearch indices.stats failed for %s: %s", self.kb_name, exc)
            return 0
        try:
            return int(stats["_all"]["total"]["store"]["size_in_bytes"])
        except (KeyError, TypeError, ValueError):
            return 0

    async def teardown(self) -> None:
        client = getattr(self, "_os_client", None)
        if client is not None and hasattr(client, "close"):
            try:
                await asyncio.to_thread(client.close)
            except Exception as exc:  # noqa: BLE001
                # ``teardown`` runs in ``finally`` blocks; a leaked
                # connection during shutdown is worth a default-level
                # warning so it doesn't silently exhaust pool slots.
                logger.warning("OpenSearch client.close failed: %s", exc)
        self._os_client = None
        self._vector_store = None

    async def delete_collection(self) -> None:
        """Drop the configured index. Used by KB deletion."""
        client = getattr(self, "_os_client", None)
        if client is None:
            _ = self.vector_store
            client = self._os_client
        try:
            await asyncio.to_thread(client.indices.delete, index=self._os_index, ignore_unavailable=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenSearch indices.delete failed for %s: %s", self.kb_name, exc)

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
  Defaults to ``vector_field``.
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
    drain_queue_until_sentinel,
)
from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langchain_core.vectorstores import VectorStore


DEFAULT_URL_VARIABLE = "OPENSEARCH_URL"
DEFAULT_USERNAME_VARIABLE = "OPENSEARCH_USERNAME"
DEFAULT_PASSWORD_VARIABLE = "OPENSEARCH_PASSWORD"  # noqa: S105 — variable name, not a secret  # pragma: allowlist secret
DEFAULT_VECTOR_FIELD = "vector_field"
DEFAULT_TEXT_FIELD = "text"
DEFAULT_ENGINE = "jvector"
DEFAULT_SPACE_TYPE = "l2"


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
        use_ssl = bool(self.backend_config.get("use_ssl", True))
        verify_certs = bool(self.backend_config.get("verify_certs", True))

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
            logger.debug("OpenSearch count() failed for %s: %s", self.kb_name, exc)
            return 0

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
        # Skip the embedding column in ``_source`` when the caller doesn't
        # need it — large embedding vectors dominate scroll payloads.
        source_excludes = None if include_embeddings else [vector_field]

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
                        metadata = {k: v for k, v in source.items() if k not in {text_field, vector_field, "metadata"}}
                    embedding: list[float] | None = None
                    if include_embeddings:
                        raw_vec = source.get(vector_field)
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
                        logger.debug("OpenSearch scan close failed: %s", exc)
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
                    logger.debug("OpenSearch iter_documents worker failed: %s", item)
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

        ``where`` is translated to a bool-must match query on top-level
        ``_source`` fields. This mirrors what the Mongo backend does
        with its filter dict — keeping the cross-backend surface simple
        rather than exposing the full OpenSearch DSL.
        """
        await self.ensure_ready()
        client = getattr(self, "_os_client", None)
        if client is None:
            _ = self.vector_store
            client = self._os_client
        if not where:
            return
        must = [{"match": {key: value}} for key, value in where.items()]
        body = {"query": {"bool": {"must": must}}}
        try:
            await asyncio.to_thread(
                client.delete_by_query,
                index=self._os_index,
                body=body,
                refresh=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("OpenSearch delete_by_query failed for %s: %s", self.kb_name, exc)

    async def storage_size_bytes(self) -> int:
        await self.ensure_ready()
        client = getattr(self, "_os_client", None)
        if client is None:
            return 0
        try:
            stats = await asyncio.to_thread(client.indices.stats, index=self._os_index)
        except Exception as exc:  # noqa: BLE001
            logger.debug("OpenSearch indices.stats failed for %s: %s", self.kb_name, exc)
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
                logger.debug("OpenSearch client.close failed: %s", exc)
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
            logger.debug("OpenSearch indices.delete failed for %s: %s", self.kb_name, exc)

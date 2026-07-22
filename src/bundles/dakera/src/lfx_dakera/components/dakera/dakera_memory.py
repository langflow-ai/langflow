"""Dakera Memory component for Langflow.

A single node that speaks the full Dakera memory REST API of a self-hosted
Dakera server. The **Mode** dropdown selects the operation and the node only
shows the fields relevant to it:

* **Recall**  — decay-weighted semantic recall (importance + recency aware).
* **Search**  — filterable browse (tags, importance range, sort order).
* **Store**   — persist a new memory with importance, tags, TTL and metadata.
* **Get**     — fetch a single memory by ID.
* **Update**  — patch content / importance / tags / metadata of a memory.
* **Forget**  — delete memories by ID, tags, session or importance threshold.

Dakera REST API (self-hosted, default port 3000 — see ``dakera-ai/dakera-deploy``):
  POST /v1/memory/store        { content, agent_id, importance?, tags?, ... }
  POST /v1/memory/recall       { query, agent_id, top_k?, ... }
  POST /v1/memory/search       { agent_id, query?, tags?, sort_by?, ... }
  GET  /v1/memory/get/{id}      ?agent_id=<id>
  PUT  /v1/memory/update/{id}   ?agent_id=<id>   { content?, importance?, ... }
  POST /v1/memory/forget       { agent_id, memory_ids?, tags?, ... }

Recall/Search return ``{ memories: [{ memory, score, smart_score? }] }``;
store/get/update return a bare ``Memory`` (store wraps it in ``memory``).

Auth: optional ``Authorization: Bearer <api_key>`` header (keys look like ``dk-…``).

Quick-start (self-hosting bundles a MinIO object store — do not run the image bare):
    git clone https://github.com/dakera-ai/dakera-deploy && cd dakera-deploy
    docker compose -f docker/docker-compose.yml up -d   # server on :3000
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import (
    BoolInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    SecretStrInput,
)
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

if TYPE_CHECKING:
    from lfx.schema.dotdict import dotdict

_DEFAULT_URL = "http://localhost:3000"
_DEFAULT_AGENT = "langflow-agent"
_DEFAULT_IMPORTANCE = 0.5
_MIN_IMPORTANCE = 0.0
_MAX_IMPORTANCE = 1.0
_DEFAULT_TOP_K = 5
_MAX_TOP_K = 100
_TIMEOUT_S = 15.0
_HTTP_ERROR_STATUS = 400
_DETAIL_MAX = 300

_SORT_FIELDS = ["relevance", "created_at", "last_accessed_at", "importance", "access_count"]


class DakeraMemoryComponent(Component):
    """Langflow node that connects to a self-hosted Dakera memory server.

    One node, six operations, selected by the **Mode** dropdown. Every mode is
    scoped to ``agent_id`` (the memory namespace). Recall and Search return a
    :class:`DataFrame` of ranked memories; Store/Get/Update return a single-row
    :class:`DataFrame` for the affected memory; Forget returns the delete count.

    Hard failures (connection refused, HTTP >= 400) raise ``ValueError`` with the
    server's detail so the error surfaces on the node rather than corrupting a
    downstream flow with a silent empty result.
    """

    display_name = "Dakera Memory"
    description = (
        "Store, recall, search, get, update and forget memories on a self-hosted Dakera server "
        "(https://dakera.ai). Decay-weighted importance, session scoping, tags and metadata."
    )
    documentation = "https://dakera.ai/docs"
    name = "DakeraMemory"
    icon = "database"

    MODES = ["Recall", "Search", "Store", "Get", "Update", "Forget"]

    # Fields always visible regardless of mode (connection + namespace).
    default_keys = ["mode", "api_url", "api_key", "agent_id", "verify_ssl"]

    # Fields surfaced for each mode (on top of ``default_keys``).
    mode_config = {
        "Store": ["content", "importance", "tags", "metadata", "session_id", "ttl_seconds"],
        "Recall": ["query", "top_k", "min_importance", "session_id"],
        "Search": ["query", "top_k", "tags", "min_importance", "sort_by", "session_id"],
        "Get": ["memory_id"],
        "Update": ["memory_id", "content", "importance", "tags", "metadata"],
        "Forget": ["memory_id", "tags", "session_id", "below_importance"],
    }

    # Every field that is toggled by mode (i.e. declared ``dynamic=True``). A
    # field can appear in several modes, so visibility is computed by explicit
    # membership rather than the shared ``set_current_fields`` helper (which
    # last-write-hides fields present in more than one action list).
    _dynamic_fields = [
        "query",
        "top_k",
        "min_importance",
        "sort_by",
        "memory_id",
        "content",
        "importance",
        "tags",
        "metadata",
        "ttl_seconds",
        "below_importance",
        "session_id",
    ]

    # ------------------------------------------------------------------ #
    #  Inputs
    # ------------------------------------------------------------------ #

    inputs = [
        DropdownInput(
            name="mode",
            display_name="Mode",
            options=MODES,
            value="Recall",
            info="Operation to perform against the Dakera server.",
            real_time_refresh=True,
        ),
        # ---- connection --------------------------------------------------
        MessageTextInput(
            name="api_url",
            display_name="Dakera API URL",
            info="Base URL of your Dakera instance, e.g. http://localhost:3000",
            value=_DEFAULT_URL,
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Bearer token for Dakera (looks like 'dk-…'). Leave empty for unauthenticated local dev.",
            required=False,
            value="",
        ),
        MessageTextInput(
            name="agent_id",
            display_name="Agent ID",
            info="Namespace for memories. All operations are scoped to this ID.",
            required=True,
            value=_DEFAULT_AGENT,
            tool_mode=True,
        ),
        BoolInput(
            name="verify_ssl",
            display_name="Verify SSL",
            info="Verify TLS certificates. Disable only for self-signed certs in development.",
            value=True,
            advanced=True,
        ),
        # ---- read (Recall / Search) --------------------------------------
        MessageTextInput(
            name="query",
            display_name="Query",
            info="Natural-language query for semantic recall / search.",
            tool_mode=True,
            dynamic=True,
            show=True,
        ),
        IntInput(
            name="top_k",
            display_name="Top K",
            info="Maximum number of memories to retrieve (1-100).",
            value=_DEFAULT_TOP_K,
            dynamic=True,
            show=True,
        ),
        FloatInput(
            name="min_importance",
            display_name="Min Importance",
            info="Only return memories with importance >= this value (0.0 keeps all).",
            value=0.0,
            advanced=True,
            dynamic=True,
            show=True,
        ),
        DropdownInput(
            name="sort_by",
            display_name="Sort By",
            options=_SORT_FIELDS,
            value="relevance",
            info="Search ordering. 'relevance' uses the ranked score; others sort by that field.",
            advanced=True,
            dynamic=True,
            show=False,
        ),
        # ---- single-memory ops (Get / Update / Forget) -------------------
        MessageTextInput(
            name="memory_id",
            display_name="Memory ID",
            info="ID of the memory to get, update, or forget.",
            tool_mode=True,
            dynamic=True,
            show=False,
        ),
        # ---- write (Store / Update) --------------------------------------
        MultilineInput(
            name="content",
            display_name="Content",
            info="Text to store, or the new content when updating a memory.",
            tool_mode=True,
            dynamic=True,
            show=False,
        ),
        FloatInput(
            name="importance",
            display_name="Importance",
            info=(
                "Importance score (0.0-1.0). Decays over time based on access. "
                "On Update, leave at 0.5 to keep the current importance unchanged."
            ),
            value=_DEFAULT_IMPORTANCE,
            dynamic=True,
            show=False,
        ),
        MessageTextInput(
            name="tags",
            display_name="Tags",
            info="Comma-separated tags (e.g. 'preference,decision'). Used to categorise, filter or forget.",
            value="",
            dynamic=True,
            show=False,
        ),
        MultilineInput(
            name="metadata",
            display_name="Metadata (JSON)",
            info="Optional JSON object of arbitrary metadata to attach to the memory.",
            value="",
            advanced=True,
            dynamic=True,
            show=False,
        ),
        IntInput(
            name="ttl_seconds",
            display_name="TTL (seconds)",
            info="Optional time-to-live. The memory is hard-deleted after this many seconds (0 = no TTL).",
            value=0,
            advanced=True,
            dynamic=True,
            show=False,
        ),
        # ---- forget selector --------------------------------------------
        FloatInput(
            name="below_importance",
            display_name="Forget Below Importance",
            info="Forget memories with importance below this value (0.0 = disabled).",
            value=0.0,
            dynamic=True,
            show=False,
        ),
        # ---- shared scope ------------------------------------------------
        MessageTextInput(
            name="session_id",
            display_name="Session ID",
            info="Optional session scope for the operation.",
            value="",
            advanced=True,
            dynamic=True,
            show=False,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="dataframe", method="run_action"),
    ]

    # ------------------------------------------------------------------ #
    #  Dynamic field visibility
    # ------------------------------------------------------------------ #

    def update_build_config(
        self,
        build_config: dotdict,
        field_value: Any,  # noqa: ARG002
        field_name: str | None = None,
    ) -> dotdict:
        """Show only the fields relevant to the selected mode."""
        if field_name not in (None, "mode"):
            return build_config
        mode = (build_config.get("mode", {}) or {}).get("value") or "Recall"
        visible = set(self.mode_config.get(mode, []))
        for name in self._dynamic_fields:
            field = build_config.get(name)
            if isinstance(field, dict) and "show" in field:
                field["show"] = name in visible
        return build_config

    # ------------------------------------------------------------------ #
    #  Dispatch
    # ------------------------------------------------------------------ #

    def run_action(self) -> DataFrame:
        """Run the operation selected by ``mode`` and return the result as a DataFrame."""
        mode = (self.mode or "Recall").strip()
        handlers = {
            "Store": self._store,
            "Recall": self._recall,
            "Search": self._search,
            "Get": self._get,
            "Update": self._update,
            "Forget": self._forget,
        }
        handler = handlers.get(mode)
        if handler is None:
            msg = f"Unknown Dakera mode: {mode!r}. Expected one of {self.MODES}."
            raise ValueError(msg)
        return handler()

    # ------------------------------------------------------------------ #
    #  HTTP + parsing helpers
    # ------------------------------------------------------------------ #

    def _client(self) -> httpx.Client:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        api_key = (self.api_key or "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return httpx.Client(
            base_url=(self.api_url or _DEFAULT_URL).rstrip("/"),
            headers=headers,
            verify=bool(self.verify_ssl),
            timeout=_TIMEOUT_S,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
    ) -> Any:
        """Perform an HTTP call, raising ``ValueError`` with server detail on failure."""
        try:
            with self._client() as client:
                resp = client.request(method, path, json=json_body, params=params)
        except httpx.RequestError as exc:
            msg = f"Could not reach Dakera at {self.api_url!r}: {exc}"
            raise ValueError(msg) from exc
        if resp.status_code >= _HTTP_ERROR_STATUS:
            detail = resp.text[:_DETAIL_MAX]
            msg = f"Dakera {method} {path} failed: HTTP {resp.status_code} — {detail}"
            raise ValueError(msg)
        if not resp.content:
            return {}
        return resp.json()

    def _agent_id(self) -> str:
        return (self.agent_id or "").strip() or _DEFAULT_AGENT

    def _session(self) -> str | None:
        return (self.session_id or "").strip() or None

    def _top_k(self) -> int:
        return max(1, min(_MAX_TOP_K, int(self.top_k or _DEFAULT_TOP_K)))

    @staticmethod
    def _split_tags(raw: str | None) -> list[str]:
        return [t.strip() for t in (raw or "").split(",") if t.strip()]

    @staticmethod
    def _validate_importance(value: float, field: str) -> float:
        val = float(value)
        if not (_MIN_IMPORTANCE <= val <= _MAX_IMPORTANCE):
            msg = f"`{field}` must be between {_MIN_IMPORTANCE} and {_MAX_IMPORTANCE}, got {val}."
            raise ValueError(msg)
        return val

    def _parse_metadata(self) -> dict | None:
        raw = (self.metadata or "").strip()
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            msg = f"`metadata` must be valid JSON: {exc}"
            raise ValueError(msg) from exc
        if not isinstance(parsed, dict):
            msg = '`metadata` must be a JSON object (e.g. {"source": "chat"}).'
            raise TypeError(msg)
        return parsed

    @staticmethod
    def _memory_row(mem: dict) -> dict:
        return {
            "id": mem.get("id", ""),
            "content": mem.get("content", ""),
            "importance": mem.get("importance"),
            "memory_type": mem.get("memory_type"),
            "tags": mem.get("tags", []),
            "agent_id": mem.get("agent_id", ""),
            "session_id": mem.get("session_id"),
            "metadata": mem.get("metadata"),
            "created_at": mem.get("created_at"),
            "last_accessed_at": mem.get("last_accessed_at"),
            "access_count": mem.get("access_count"),
        }

    def _results_to_rows(self, items: list[dict]) -> list[Data]:
        rows: list[Data] = []
        for item in items:
            mem = item.get("memory") or {}
            if not mem:
                continue
            row = self._memory_row(mem)
            row["score"] = round(float(item.get("score", 0.0)), 4)
            if item.get("smart_score") is not None:
                row["smart_score"] = round(float(item["smart_score"]), 4)
            rows.append(Data(data=row))
        return rows

    # ------------------------------------------------------------------ #
    #  Operations
    # ------------------------------------------------------------------ #

    def _store(self) -> DataFrame:
        content = (self.content or "").strip()
        if not content:
            msg = "`content` is required to store a memory."
            raise ValueError(msg)
        body: dict = {
            "content": content,
            "agent_id": self._agent_id(),
            "importance": self._validate_importance(self.importance or _DEFAULT_IMPORTANCE, "importance"),
        }
        if sid := self._session():
            body["session_id"] = sid
        if tags := self._split_tags(self.tags):
            body["tags"] = tags
        if (metadata := self._parse_metadata()) is not None:
            body["metadata"] = metadata
        if (ttl := int(self.ttl_seconds or 0)) > 0:
            body["ttl_seconds"] = ttl

        payload = self._request("POST", "/v1/memory/store", json_body=body)
        mem = payload.get("memory", {})
        self.status = f"Stored memory {mem.get('id', '?')}"
        return DataFrame([Data(data=self._memory_row(mem))])

    def _recall(self) -> DataFrame:
        query = (self.query or "").strip()
        if not query:
            msg = "`query` is required to recall memories."
            raise ValueError(msg)
        body: dict = {"query": query, "agent_id": self._agent_id(), "top_k": self._top_k()}
        if sid := self._session():
            body["session_id"] = sid
        if (min_imp := float(self.min_importance or 0.0)) > 0:
            body["min_importance"] = self._validate_importance(min_imp, "min_importance")

        payload = self._request("POST", "/v1/memory/recall", json_body=body)
        rows = self._results_to_rows(payload.get("memories", []))
        self.status = f"Recalled {len(rows)} memories"
        return DataFrame(rows)

    def _search(self) -> DataFrame:
        body: dict = {"agent_id": self._agent_id(), "top_k": self._top_k()}
        if query := (self.query or "").strip():
            body["query"] = query
        if tags := self._split_tags(self.tags):
            body["tags"] = tags
        if (min_imp := float(self.min_importance or 0.0)) > 0:
            body["min_importance"] = self._validate_importance(min_imp, "min_importance")
        if (sort_by := (self.sort_by or "").strip()) and sort_by != "relevance":
            body["sort_by"] = sort_by
        if sid := self._session():
            body["session_id"] = sid

        payload = self._request("POST", "/v1/memory/search", json_body=body)
        rows = self._results_to_rows(payload.get("memories", []))
        self.status = f"Found {len(rows)} memories"
        return DataFrame(rows)

    def _get(self) -> DataFrame:
        memory_id = (self.memory_id or "").strip()
        if not memory_id:
            msg = "`memory_id` is required to get a memory."
            raise ValueError(msg)
        payload = self._request(
            "GET",
            f"/v1/memory/get/{memory_id}",
            params={"agent_id": self._agent_id()},
        )
        self.status = f"Retrieved memory {memory_id}"
        return DataFrame([Data(data=self._memory_row(payload))])

    def _update(self) -> DataFrame:
        memory_id = (self.memory_id or "").strip()
        if not memory_id:
            msg = "`memory_id` is required to update a memory."
            raise ValueError(msg)
        body: dict = {}
        if content := (self.content or "").strip():
            body["content"] = content
        importance = float(self.importance or _DEFAULT_IMPORTANCE)
        if importance != _DEFAULT_IMPORTANCE:
            body["importance"] = self._validate_importance(importance, "importance")
        if tags := self._split_tags(self.tags):
            body["tags"] = tags
        if (metadata := self._parse_metadata()) is not None:
            body["metadata"] = metadata
        if not body:
            msg = "Update requires at least one field to change (content, importance, tags or metadata)."
            raise ValueError(msg)

        payload = self._request(
            "PUT",
            f"/v1/memory/update/{memory_id}",
            json_body=body,
            params={"agent_id": self._agent_id()},
        )
        self.status = f"Updated memory {memory_id}"
        return DataFrame([Data(data=self._memory_row(payload))])

    def _forget(self) -> DataFrame:
        memory_id = (self.memory_id or "").strip()
        tags = self._split_tags(self.tags)
        sid = self._session()
        below = float(self.below_importance or 0.0)
        below_val = below if below > 0 else None

        # Mass-delete guard: a bare agent_id forget would wipe the whole namespace.
        if not (memory_id or tags or sid or below_val is not None):
            msg = (
                "Forget requires at least one selector (memory_id, tags, session_id, or "
                "below_importance) to prevent deleting every memory for this agent."
            )
            raise ValueError(msg)

        body: dict = {"agent_id": self._agent_id()}
        if memory_id:
            body["memory_ids"] = [memory_id]
        if tags:
            body["tags"] = tags
        if sid:
            body["session_id"] = sid
        if below_val is not None:
            body["below_importance"] = self._validate_importance(below_val, "below_importance")

        payload = self._request("POST", "/v1/memory/forget", json_body=body)
        deleted = int(payload.get("deleted_count", 0))
        self.status = f"Forgot {deleted} memories"
        return DataFrame([Data(data={"deleted_count": deleted, "agent_id": self._agent_id()})])

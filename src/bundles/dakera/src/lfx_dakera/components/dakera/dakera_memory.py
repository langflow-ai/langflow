"""Dakera Memory component for Langflow.

Provides two independent outputs:
  - store_memory  → stores a message in Dakera and returns the stored record as Data
  - search_memories → semantic search against Dakera, returns ranked hits as list[Data]

Dakera REST API (self-hosted, default port 3300):
  POST /v1/memory/store  { content, agent_id, session_id?, importance?, tags?, metadata? }
  POST /v1/memory/search { agent_id, query, top_k?, session_id? }
    → { memories: [{ memory: { id, content, metadata? }, score }] }

Auth: optional ``Authorization: Bearer <api_key>`` header.

Quick-start:
    docker run -p 3300:3300 -e DAKERA_API_KEY=demo ghcr.io/dakera-ai/dakera:latest
"""

from __future__ import annotations

import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import (
    BoolInput,
    FloatInput,
    IntInput,
    MessageTextInput,
    SecretStrInput,
)
from lfx.schema.data import Data
from lfx.template.field.base import Output

_DEFAULT_IMPORTANCE = 0.5


class DakeraMemoryComponent(Component):
    """Langflow node that connects to a self-hosted Dakera memory server.

    Exposes two independent outputs:

    * **Store** — writes ``content`` into Dakera for ``agent_id`` and returns
      the stored memory record as a ``Data`` object.
    * **Search** — runs a semantic search in Dakera using ``search_query`` and
      returns a list of scored ``Data`` records, ordered by relevance.

    Both operations degrade gracefully on error: an error key is present on the
    returned ``Data`` rather than raising, so downstream nodes are not blocked.
    """

    display_name = "Dakera Memory"
    description = (
        "Store and semantically search memories using a self-hosted Dakera server "
        "(https://dakera.ai). Supports decay-weighted importance, session scoping, "
        "and arbitrary metadata tagging."
    )
    name = "DakeraMemory"
    icon = "database"

    # ------------------------------------------------------------------ #
    #  Inputs
    # ------------------------------------------------------------------ #

    inputs = [
        # ---- connection --------------------------------------------------
        MessageTextInput(
            name="api_url",
            display_name="Dakera API URL",
            info="Base URL of your Dakera instance, e.g. http://localhost:3300",
            value="http://localhost:3300",
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Bearer token for Dakera authentication. Leave empty for unauthenticated local dev.",
            required=False,
            value="",
        ),
        # ---- namespace ---------------------------------------------------
        MessageTextInput(
            name="agent_id",
            display_name="Agent ID",
            info="Namespace for memories. All store/search calls are scoped to this ID.",
            required=True,
            value="langflow-agent",
            tool_mode=True,
        ),
        MessageTextInput(
            name="session_id",
            display_name="Session ID",
            info="Optional session scope. When set, only memories from this session are searched.",
            required=False,
            value="",
            advanced=True,
        ),
        # ---- store inputs ------------------------------------------------
        MessageTextInput(
            name="content",
            display_name="Content",
            info="Text to store in Dakera memory.",
            required=False,
            tool_mode=True,
        ),
        FloatInput(
            name="importance",
            display_name="Importance",
            info="Initial importance score for the stored memory (0.0 - 1.0). "
            "Decays over time based on access patterns.",
            value=_DEFAULT_IMPORTANCE,
            required=False,
            advanced=True,
        ),
        MessageTextInput(
            name="tags",
            display_name="Tags",
            info="Comma-separated tags for categorising this memory (e.g. 'preference,decision').",
            required=False,
            value="",
            advanced=True,
        ),
        # ---- search inputs -----------------------------------------------
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
            info="Natural-language query for semantic memory search.",
            required=False,
            tool_mode=True,
        ),
        IntInput(
            name="top_k",
            display_name="Top K",
            info="Maximum number of memories to retrieve (1-20).",
            value=5,
            required=False,
            advanced=True,
        ),
        # ---- connection options ------------------------------------------
        BoolInput(
            name="verify_ssl",
            display_name="Verify SSL",
            info="Verify TLS certificates. Disable only for self-signed certs in development.",
            value=True,
            required=False,
            advanced=True,
        ),
    ]

    # ------------------------------------------------------------------ #
    #  Outputs
    # ------------------------------------------------------------------ #

    outputs = [
        Output(
            display_name="Stored Memory",
            name="stored_memory",
            method="store_memory",
        ),
        Output(
            display_name="Search Results",
            name="search_results",
            method="search_memories",
        ),
    ]

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _client(self) -> httpx.Client:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        api_key = (self.api_key or "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return httpx.Client(
            base_url=(self.api_url or "http://localhost:3300").rstrip("/"),
            headers=headers,
            verify=bool(self.verify_ssl),
            timeout=15.0,
        )

    def _session_id(self) -> str | None:
        sid = (self.session_id or "").strip()
        return sid if sid else None

    # ------------------------------------------------------------------ #
    #  Output methods
    # ------------------------------------------------------------------ #

    def store_memory(self) -> Data:
        """Store ``content`` in Dakera and return the stored memory record."""
        content = (self.content or "").strip()
        if not content:
            return Data(data={"error": "content is required for store_memory"})

        body: dict = {
            "content": content,
            "agent_id": self.agent_id or "langflow-agent",
        }
        sid = self._session_id()
        if sid:
            body["session_id"] = sid
        importance = float(self.importance or _DEFAULT_IMPORTANCE)
        if importance != _DEFAULT_IMPORTANCE:
            body["importance"] = importance
        tags_raw = (self.tags or "").strip()
        if tags_raw:
            body["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]

        try:
            with self._client() as client:
                resp = client.post("/v1/memory/store", json=body)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPStatusError as exc:
            return Data(data={"error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"})
        except httpx.RequestError as exc:
            return Data(data={"error": f"Connection error: {exc}"})

        memory = payload.get("memory", {})
        result = Data(
            data={
                "id": memory.get("id", ""),
                "content": memory.get("content", content),
                "agent_id": memory.get("agent_id", self.agent_id),
                "session_id": memory.get("session_id", sid),
            }
        )
        self.status = f"Stored (id={memory.get('id', '?')})"
        return result

    def search_memories(self) -> list[Data]:
        """Search Dakera for memories matching ``search_query``."""
        query = (self.search_query or "").strip()
        if not query:
            return [Data(data={"error": "search_query is required for search_memories"})]

        top_k = max(1, min(20, int(self.top_k or 5)))
        body: dict = {
            "agent_id": self.agent_id or "langflow-agent",
            "query": query,
            "top_k": top_k,
        }
        sid = self._session_id()
        if sid:
            body["session_id"] = sid

        try:
            with self._client() as client:
                resp = client.post("/v1/memory/search", json=body)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPStatusError as exc:
            return [Data(data={"error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"})]
        except httpx.RequestError as exc:
            return [Data(data={"error": f"Connection error: {exc}"})]

        memories = payload.get("memories", [])
        if not memories:
            self.status = "No results"
            return []

        results = [
            Data(
                data={
                    "id": item["memory"]["id"],
                    "content": item["memory"]["content"],
                    "score": round(item["score"], 4),
                    "agent_id": item["memory"].get("agent_id", ""),
                    "session_id": item["memory"].get("session_id"),
                    "metadata": item["memory"].get("metadata", {}),
                }
            )
            for item in memories
            if "memory" in item
        ]
        self.status = f"{len(results)} results"
        return results

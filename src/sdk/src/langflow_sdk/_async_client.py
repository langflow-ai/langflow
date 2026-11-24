"""Async HTTP client for the Langflow REST API.

Preferred usage via the short alias::

    from langflow_sdk import AsyncClient

    async with AsyncClient("https://langflow.example.com", api_key="...") as client:
        flows = await client.list_flows()
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import httpx

from langflow_sdk._client_common import _ClientCommon
from langflow_sdk._http import (
    _DEFAULT_TIMEOUT,
    _build_headers,
    _connection_error,
    _logger,
    _raise_for_status,
    _raise_for_status_code,
)
from langflow_sdk.background_job import BackgroundJob
from langflow_sdk.models import (
    Flow,
    FlowCreate,
    FlowUpdate,
    Project,
    ProjectCreate,
    ProjectUpdate,
    ProjectWithFlows,
    RunRequest,
    RunResponse,
    StreamChunk,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path
    from uuid import UUID

    from typing_extensions import Self


class AsyncLangflowClient(_ClientCommon):
    """Async client for the Langflow REST API.

    Prefer the short alias :data:`AsyncClient` for new code::

        from langflow_sdk import AsyncClient

        async with AsyncClient("https://langflow.example.com", api_key="...") as client:
            flows = await client.list_flows()
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        httpx_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._owns_client = httpx_client is None
        self._http = httpx_client or httpx.AsyncClient(
            base_url=self._base_url,
            headers=_build_headers(api_key),
            timeout=timeout,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            response = await self._http.request(
                method,
                path,
                json=json,
                params=params,
                content=content,
                headers=headers,
            )
        except httpx.ConnectError as exc:
            _logger.debug("Connection error to %s", self._base_url, exc_info=True)
            raise _connection_error(self._base_url, exc) from exc
        _logger.debug("HTTP %s %s -> %s", method, path, response.status_code)
        _raise_for_status(response)
        return response

    # ------------------------------------------------------------------
    # Flows
    # ------------------------------------------------------------------

    async def list_flows(
        self,
        *,
        folder_id: UUID | str | None = None,
        remove_example_flows: bool = False,
        components_only: bool = False,
        get_all: bool = False,
        header_flows: bool = False,
        page: int = 1,
        size: int = 50,
    ) -> list[Flow]:
        resp = await self._request(
            "GET",
            "/api/v1/flows/",
            params=self._build_flow_list_params(
                folder_id=folder_id,
                remove_example_flows=remove_example_flows,
                components_only=components_only,
                get_all=get_all,
                header_flows=header_flows,
                page=page,
                size=size,
            ),
        )
        return self._validate_model_list(Flow, resp.json())

    async def get_flow(self, flow_id: UUID | str) -> Flow:
        resp = await self._request("GET", f"/api/v1/flows/{flow_id}")
        return self._validate_model(Flow, resp.json())

    async def create_flow(self, flow: FlowCreate) -> Flow:
        resp = await self._request("POST", "/api/v1/flows/", json=self._model_payload(flow))
        return self._validate_model(Flow, resp.json())

    async def update_flow(self, flow_id: UUID | str, update: FlowUpdate) -> Flow:
        resp = await self._request(
            "PATCH",
            f"/api/v1/flows/{flow_id}",
            json=self._model_payload(update),
        )
        return self._validate_model(Flow, resp.json())

    async def upsert_flow(self, flow_id: UUID | str, flow: FlowCreate) -> tuple[Flow, bool]:
        """Create-or-update by stable ID. Returns ``(flow, created)``."""
        resp = await self._request(
            "PUT",
            f"/api/v1/flows/{flow_id}",
            json=self._model_payload(flow),
        )
        return self._upsert_result(Flow, resp)

    async def delete_flow(self, flow_id: UUID | str) -> None:
        await self._request("DELETE", f"/api/v1/flows/{flow_id}")

    async def run_flow(
        self,
        flow_id_or_endpoint: UUID | str,
        request: RunRequest,
    ) -> RunResponse:
        resp = await self._request(
            "POST",
            f"/api/v1/run/{flow_id_or_endpoint}",
            json=self._model_payload(request),
        )
        return self._validate_model(RunResponse, resp.json())

    async def run(
        self,
        flow_id_or_endpoint: UUID | str,
        input_value: str = "",
        *,
        input_type: str = "chat",
        output_type: str = "chat",
        tweaks: dict[str, Any] | None = None,
    ) -> RunResponse:
        """Run a flow and return the full response.

        Convenience wrapper around :meth:`run_flow` that accepts plain keyword
        arguments instead of a :class:`RunRequest`::

            result = await client.run("my-flow", input_value="Hello")
            print(result.first_text_output())
        """
        return await self.run_flow(
            flow_id_or_endpoint,
            self._build_run_request(
                input_value=input_value,
                input_type=input_type,
                output_type=output_type,
                tweaks=tweaks,
            ),
        )

    async def run_background(
        self,
        flow_id_or_endpoint: UUID | str,
        input_value: str = "",
        *,
        input_type: str = "chat",
        output_type: str = "chat",
        tweaks: dict[str, Any] | None = None,
    ) -> BackgroundJob:
        """Start a flow run as a background asyncio task and return immediately.

        The returned :class:`BackgroundJob` lets you poll status or await
        completion without blocking the event loop::

            job = await client.run_background("my-flow", input_value="Hello!")

            # ...do other work...

            response = await job.wait_for_completion(timeout=60.0)
            print(response.get_chat_output())

        Args:
            flow_id_or_endpoint: Flow UUID or named endpoint.
            input_value: Text input passed to the flow.
            input_type: Langflow input type (default ``"chat"``).
            output_type: Langflow output type (default ``"chat"``).
            tweaks: Optional component tweaks dict.

        Returns:
            A :class:`BackgroundJob` wrapping the in-flight asyncio task.

        Adapted from ``BackgroundJob`` in langflow-ai/sdk PR #1
        (Janardan Singh Kavia, IBM Corp., Apache 2.0).
        """
        task: asyncio.Task[RunResponse] = asyncio.create_task(
            self.run(
                flow_id_or_endpoint,
                input_value,
                input_type=input_type,
                output_type=output_type,
                tweaks=tweaks,
            )
        )
        return BackgroundJob(task)

    def stream(
        self,
        flow_id_or_endpoint: UUID | str,
        input_value: str = "",
        *,
        input_type: str = "chat",
        output_type: str = "chat",
        tweaks: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a flow run, yielding :class:`StreamChunk` objects as they arrive.

        Uses server-sent events (SSE) to receive incremental output::

            async for chunk in client.stream("my-flow", input_value="Hello"):
                if chunk.is_token:
                    print(chunk.text, end="", flush=True)
                elif chunk.is_end:
                    response = chunk.final_response()
        """
        return self._aiter_stream(
            f"/api/v1/run/{flow_id_or_endpoint}",
            self._build_stream_payload(
                input_value=input_value,
                input_type=input_type,
                output_type=output_type,
                tweaks=tweaks,
            ),
        )

    async def _aiter_stream(self, path: str, payload: dict[str, Any]) -> AsyncIterator[StreamChunk]:
        """Open a streaming POST request and async-yield parsed event chunks."""
        try:
            async with self._http.stream("POST", path, json=payload) as response:
                if not response.is_success:
                    body = await response.aread()
                    _raise_for_status_code(response.status_code, self._extract_error_detail(body))
                async for line in response.aiter_lines():
                    raw = line.strip()
                    if not raw:
                        continue
                    chunk = self._parse_stream_chunk(raw)
                    if chunk is not None:
                        yield chunk
        except httpx.ConnectError as exc:
            raise _connection_error(self._base_url, exc) from exc

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    async def list_projects(self) -> list[Project]:
        resp = await self._request("GET", "/api/v1/projects/")
        return self._validate_model_list(Project, resp.json())

    async def get_project(self, project_id: UUID | str) -> ProjectWithFlows:
        resp = await self._request("GET", f"/api/v1/projects/{project_id}")
        return self._validate_model(ProjectWithFlows, resp.json())

    async def create_project(self, project: ProjectCreate) -> Project:
        resp = await self._request("POST", "/api/v1/projects/", json=self._model_payload(project))
        return self._validate_model(Project, resp.json())

    async def update_project(self, project_id: UUID | str, update: ProjectUpdate) -> Project:
        resp = await self._request(
            "PATCH",
            f"/api/v1/projects/{project_id}",
            json=self._model_payload(update),
        )
        return self._validate_model(Project, resp.json())

    async def delete_project(self, project_id: UUID | str) -> None:
        await self._request("DELETE", f"/api/v1/projects/{project_id}")

    async def download_project(self, project_id: UUID | str) -> dict[str, bytes]:
        """Download all flows in a project.

        Raises :class:`ValueError` if the archive contains more than 500
        entries or any single entry exceeds 50 MB (zip-bomb protection).
        """
        resp = await self._request("GET", f"/api/v1/projects/download/{project_id}")
        return self._extract_project_archive(resp.content)

    async def upload_project(self, zip_bytes: bytes) -> list[Flow]:
        resp = await self._request(
            "POST",
            "/api/v1/projects/upload/",
            content=zip_bytes,
            headers={"Content-Type": "application/octet-stream"},
        )
        return self._validate_model_list(Flow, resp.json())

    # ------------------------------------------------------------------
    # File I/O helpers
    # ------------------------------------------------------------------

    async def push(self, path: str | Path) -> tuple[Flow, bool]:
        """Upload or update a flow from a local JSON file.

        The ``id`` field embedded in the file is used for upsert.
        Returns ``(flow, created)``::

            flow, created = await client.push("flows/my-flow.json")
        """
        flow_id, flow_create = self._load_flow_file(path)
        return await self.upsert_flow(flow_id, flow_create)

    async def pull(
        self,
        flow_id: UUID | str,
        *,
        output: str | Path | None = None,
    ) -> dict[str, Any]:
        """Download a flow and return it as a normalized dict.

        Strips volatile fields, clears secrets, and sorts keys.
        When *output* is given the JSON is also written to that path::

            data = await client.pull("my-flow-id")
            await client.pull("my-flow-id", output="flows/my-flow.json")
        """
        flow = await self.get_flow(flow_id)
        return self._normalize_and_write_flow(flow.model_dump(mode="json"), output=output)

    async def push_project(self, directory: str | Path) -> list[tuple[Flow, bool]]:
        """Push all ``*.json`` flow files in *directory* to the server concurrently.

        Returns a list of ``(flow, created)`` pairs in sorted filename order::

            results = await client.push_project("flows/my-project/")
        """
        return list(await asyncio.gather(*[self.push(path) for path in self._project_json_paths(directory)]))

    async def pull_project(
        self,
        project_id: UUID | str,
        *,
        output_dir: str | Path,
    ) -> dict[str, Path]:
        """Download all flows in a project and write them to *output_dir*.

        Each flow is normalized before being written as ``<flow-name>.json``.
        Returns ``{flow_name: file_path}``.

        .. note::
            Flows with duplicate names overwrite each other.  See
            :meth:`LangflowClient.pull_project` for details.

        ::

            written = await client.pull_project("project-id", output_dir="flows/")
        """
        return self._write_project_flows(await self.download_project(project_id), output_dir=output_dir)


# ---------------------------------------------------------------------------
# Short alias  (preferred for new code)
# ---------------------------------------------------------------------------

#: Short alias for :class:`AsyncLangflowClient`.
#:
#: Example::
#:
#:     from langflow_sdk import AsyncClient
#:     async with AsyncClient("https://langflow.example.com", api_key="...") as c:
#:         flows = await c.list_flows()
AsyncClient = AsyncLangflowClient

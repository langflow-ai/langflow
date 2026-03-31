"""Async HTTP client for the Langflow REST API.

Preferred usage via the short alias::

    from langflow_sdk import AsyncClient

    async with AsyncClient("https://langflow.example.com", api_key="...") as client:
        flows = await client.list_flows()
"""

from __future__ import annotations

import asyncio
import io
import json
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from langflow_sdk._http import (
    _DEFAULT_TIMEOUT,
    _HTTP_201_CREATED,
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
from langflow_sdk.serialization import flow_to_json, normalize_flow

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from typing_extensions import Self


class AsyncLangflowClient:
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
        params: dict[str, Any] = {
            "remove_example_flows": remove_example_flows,
            "components_only": components_only,
            "get_all": get_all,
            "header_flows": header_flows,
            "page": page,
            "size": size,
        }
        if folder_id is not None:
            params["folder_id"] = str(folder_id)
        resp = await self._request("GET", "/api/v1/flows/", params=params)
        return [Flow.model_validate(f) for f in resp.json()]

    async def get_flow(self, flow_id: UUID | str) -> Flow:
        resp = await self._request("GET", f"/api/v1/flows/{flow_id}")
        return Flow.model_validate(resp.json())

    async def create_flow(self, flow: FlowCreate) -> Flow:
        resp = await self._request("POST", "/api/v1/flows/", json=flow.model_dump(mode="json", exclude_none=True))
        return Flow.model_validate(resp.json())

    async def update_flow(self, flow_id: UUID | str, update: FlowUpdate) -> Flow:
        resp = await self._request(
            "PATCH",
            f"/api/v1/flows/{flow_id}",
            json=update.model_dump(mode="json", exclude_none=True),
        )
        return Flow.model_validate(resp.json())

    async def upsert_flow(self, flow_id: UUID | str, flow: FlowCreate) -> tuple[Flow, bool]:
        """Create-or-update by stable ID. Returns ``(flow, created)``."""
        resp = await self._request(
            "PUT",
            f"/api/v1/flows/{flow_id}",
            json=flow.model_dump(mode="json", exclude_none=True),
        )
        return Flow.model_validate(resp.json()), resp.status_code == _HTTP_201_CREATED

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
            json=request.model_dump(mode="json", exclude_none=True),
        )
        return RunResponse.model_validate(resp.json())

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
            RunRequest(
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
        payload = RunRequest(
            input_value=input_value,
            input_type=input_type,
            output_type=output_type,
            tweaks=tweaks,
            stream=True,
        ).model_dump(mode="json", exclude_none=True)
        return self._aiter_stream(f"/api/v1/run/{flow_id_or_endpoint}", payload)

    async def _aiter_stream(self, path: str, payload: dict[str, Any]) -> AsyncIterator[StreamChunk]:
        """Open a streaming POST request and async-yield parsed event chunks."""
        try:
            async with self._http.stream("POST", path, json=payload) as response:
                if not response.is_success:
                    body = await response.aread()
                    try:
                        parsed = json.loads(body)
                        detail = (
                            parsed.get("detail", body.decode(errors="replace"))
                            if isinstance(parsed, dict)
                            else body.decode(errors="replace")
                        )
                    except Exception:  # noqa: BLE001
                        detail = body.decode(errors="replace")
                    _raise_for_status_code(response.status_code, detail)
                async for line in response.aiter_lines():
                    raw = line.strip()
                    if not raw:
                        continue
                    try:
                        obj = json.loads(raw)
                        yield StreamChunk(event=obj["event"], data=obj.get("data", {}))
                    except (json.JSONDecodeError, KeyError):
                        _logger.debug("Skipping malformed SSE chunk", exc_info=True)
                        continue
        except httpx.ConnectError as exc:
            raise _connection_error(self._base_url, exc) from exc

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    async def list_projects(self) -> list[Project]:
        resp = await self._request("GET", "/api/v1/projects/")
        return [Project.model_validate(p) for p in resp.json()]

    async def get_project(self, project_id: UUID | str) -> ProjectWithFlows:
        resp = await self._request("GET", f"/api/v1/projects/{project_id}")
        return ProjectWithFlows.model_validate(resp.json())

    async def create_project(self, project: ProjectCreate) -> Project:
        resp = await self._request("POST", "/api/v1/projects/", json=project.model_dump(mode="json", exclude_none=True))
        return Project.model_validate(resp.json())

    async def update_project(self, project_id: UUID | str, update: ProjectUpdate) -> Project:
        resp = await self._request(
            "PATCH",
            f"/api/v1/projects/{project_id}",
            json=update.model_dump(mode="json", exclude_none=True),
        )
        return Project.model_validate(resp.json())

    async def delete_project(self, project_id: UUID | str) -> None:
        await self._request("DELETE", f"/api/v1/projects/{project_id}")

    _MAX_ZIP_ENTRIES = 500
    _MAX_ENTRY_BYTES = 50 * 1024 * 1024  # 50 MB per file

    async def download_project(self, project_id: UUID | str) -> dict[str, bytes]:
        """Download all flows in a project.

        Raises :class:`ValueError` if the archive contains more than 500
        entries or any single entry exceeds 50 MB (zip-bomb protection).
        """
        resp = await self._request("GET", f"/api/v1/projects/download/{project_id}")
        flows: dict[str, bytes] = {}
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            entries = zf.infolist()
            if len(entries) > self._MAX_ZIP_ENTRIES:
                msg = f"ZIP contains {len(entries)} entries, exceeding the limit of {self._MAX_ZIP_ENTRIES}"
                raise ValueError(msg)
            for info in entries:
                if info.file_size > self._MAX_ENTRY_BYTES:
                    _logger.warning(
                        "Skipping ZIP entry %r: declared size %d exceeds limit",
                        info.filename,
                        info.file_size,
                    )
                    continue
                raw = zf.read(info.filename)
                if len(raw) > self._MAX_ENTRY_BYTES:
                    _logger.warning("Skipping ZIP entry %r: actual size %d exceeds limit", info.filename, len(raw))
                    continue
                flows[info.filename] = raw
        return flows

    async def upload_project(self, zip_bytes: bytes) -> list[Flow]:
        resp = await self._request(
            "POST",
            "/api/v1/projects/upload/",
            content=zip_bytes,
            headers={"Content-Type": "application/octet-stream"},
        )
        return [Flow.model_validate(f) for f in resp.json()]

    # ------------------------------------------------------------------
    # File I/O helpers
    # ------------------------------------------------------------------

    async def push(self, path: str | Path) -> tuple[Flow, bool]:
        """Upload or update a flow from a local JSON file.

        The ``id`` field embedded in the file is used for upsert.
        Returns ``(flow, created)``::

            flow, created = await client.push("flows/my-flow.json")
        """
        path = Path(path)
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        flow_id = data.get("id")
        if not flow_id:
            msg = f"Flow file {str(path)!r} does not contain an 'id' field; cannot upsert"
            raise ValueError(msg)
        flow_create = FlowCreate.model_validate({k: v for k, v in data.items() if k != "id"})
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
        normalized = normalize_flow(flow.model_dump(mode="json"))
        if output is not None:
            out = Path(output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(flow_to_json(normalized), encoding="utf-8")
        return normalized

    async def push_project(self, directory: str | Path) -> list[tuple[Flow, bool]]:
        """Push all ``*.json`` flow files in *directory* to the server concurrently.

        Returns a list of ``(flow, created)`` pairs in sorted filename order::

            results = await client.push_project("flows/my-project/")
        """
        directory = Path(directory)
        paths = sorted(directory.glob("*.json"))
        return list(await asyncio.gather(*[self.push(p) for p in paths]))

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
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        raw_flows = await self.download_project(project_id)
        written: dict[str, Path] = {}
        for filename, content in raw_flows.items():
            data: dict[str, Any] = json.loads(content.decode("utf-8"))
            normalized = normalize_flow(data)
            name = str(normalized.get("name") or Path(filename).stem)
            dest = out / f"{name}.json"
            dest.write_text(flow_to_json(normalized), encoding="utf-8")
            written[name] = dest
        return written


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

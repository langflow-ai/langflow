"""Sync HTTP client for the Langflow REST API.

Preferred usage via the short alias::

    from langflow_sdk import Client

    client = Client("https://langflow.example.com", api_key="...")
    flows  = client.list_flows()
    result = client.run_flow("my-endpoint", RunRequest(input_value="Hello"))

The async counterpart lives in :mod:`langflow_sdk._async_client`.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

# Re-export async client so that existing ``from langflow_sdk.client import ...``
# statements continue to work without changes.
from langflow_sdk._http import (
    _DEFAULT_TIMEOUT,
    _HTTP_201_CREATED,
    _build_headers,
    _connection_error,
    _logger,
    _raise_for_status,
    _raise_for_status_code,
)
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
    from collections.abc import Iterator
    from uuid import UUID

    from typing_extensions import Self


# ---------------------------------------------------------------------------
# Synchronous client
# ---------------------------------------------------------------------------


class LangflowClient:
    """Synchronous client for the Langflow REST API.

    Prefer the short alias :data:`Client` for new code::

        from langflow_sdk import Client

        client = Client("https://langflow.example.com", api_key="...")
        flows  = client.list_flows()
        result = client.run_flow("my-endpoint", RunRequest(input_value="Hello"))
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        httpx_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._owns_client = httpx_client is None
        self._http = httpx_client or httpx.Client(
            base_url=self._base_url,
            headers=_build_headers(api_key),
            timeout=timeout,
        )

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _request(
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
            response = self._http.request(
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

    def list_flows(
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
        resp = self._request("GET", "/api/v1/flows/", params=params)
        return [Flow.model_validate(f) for f in resp.json()]

    def get_flow(self, flow_id: UUID | str) -> Flow:
        resp = self._request("GET", f"/api/v1/flows/{flow_id}")
        return Flow.model_validate(resp.json())

    def create_flow(self, flow: FlowCreate) -> Flow:
        resp = self._request("POST", "/api/v1/flows/", json=flow.model_dump(mode="json", exclude_none=True))
        return Flow.model_validate(resp.json())

    def update_flow(self, flow_id: UUID | str, update: FlowUpdate) -> Flow:
        resp = self._request(
            "PATCH",
            f"/api/v1/flows/{flow_id}",
            json=update.model_dump(mode="json", exclude_none=True),
        )
        return Flow.model_validate(resp.json())

    def upsert_flow(self, flow_id: UUID | str, flow: FlowCreate) -> tuple[Flow, bool]:
        """Create-or-update a flow by its stable ID.

        Returns ``(flow, created)`` where ``created`` is ``True`` when a new
        flow was inserted and ``False`` when an existing one was updated.
        """
        resp = self._request(
            "PUT",
            f"/api/v1/flows/{flow_id}",
            json=flow.model_dump(mode="json", exclude_none=True),
        )
        return Flow.model_validate(resp.json()), resp.status_code == _HTTP_201_CREATED

    def delete_flow(self, flow_id: UUID | str) -> None:
        self._request("DELETE", f"/api/v1/flows/{flow_id}")

    def run_flow(
        self,
        flow_id_or_endpoint: UUID | str,
        request: RunRequest,
    ) -> RunResponse:
        resp = self._request(
            "POST",
            f"/api/v1/run/{flow_id_or_endpoint}",
            json=request.model_dump(mode="json", exclude_none=True),
        )
        return RunResponse.model_validate(resp.json())

    def run(
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

            result = client.run("my-flow", input_value="Hello")
            print(result.first_text_output())
        """
        return self.run_flow(
            flow_id_or_endpoint,
            RunRequest(
                input_value=input_value,
                input_type=input_type,
                output_type=output_type,
                tweaks=tweaks,
            ),
        )

    def stream(
        self,
        flow_id_or_endpoint: UUID | str,
        input_value: str = "",
        *,
        input_type: str = "chat",
        output_type: str = "chat",
        tweaks: dict[str, Any] | None = None,
    ) -> Iterator[StreamChunk]:
        """Stream a flow run, yielding :class:`StreamChunk` objects as they arrive.

        Uses server-sent events (SSE) to receive incremental output::

            for chunk in client.stream("my-flow", input_value="Hello"):
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
        return self._iter_stream(f"/api/v1/run/{flow_id_or_endpoint}", payload)

    def _iter_stream(self, path: str, payload: dict[str, Any]) -> Iterator[StreamChunk]:
        """Open a streaming POST request and yield parsed event chunks."""
        try:
            with self._http.stream("POST", path, json=payload) as response:
                if not response.is_success:
                    body = response.read()
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
                for line in response.iter_lines():
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
    # Projects (Folders)
    # ------------------------------------------------------------------

    def list_projects(self) -> list[Project]:
        resp = self._request("GET", "/api/v1/projects/")
        return [Project.model_validate(p) for p in resp.json()]

    def get_project(self, project_id: UUID | str) -> ProjectWithFlows:
        resp = self._request("GET", f"/api/v1/projects/{project_id}")
        return ProjectWithFlows.model_validate(resp.json())

    def create_project(self, project: ProjectCreate) -> Project:
        resp = self._request("POST", "/api/v1/projects/", json=project.model_dump(mode="json", exclude_none=True))
        return Project.model_validate(resp.json())

    def update_project(self, project_id: UUID | str, update: ProjectUpdate) -> Project:
        resp = self._request(
            "PATCH",
            f"/api/v1/projects/{project_id}",
            json=update.model_dump(mode="json", exclude_none=True),
        )
        return Project.model_validate(resp.json())

    def delete_project(self, project_id: UUID | str) -> None:
        self._request("DELETE", f"/api/v1/projects/{project_id}")

    def download_project(self, project_id: UUID | str) -> dict[str, bytes]:
        """Download all flows in a project.

        Returns a mapping of ``{flow_name: raw_json_bytes}`` extracted from
        the ZIP archive returned by the server.
        """
        resp = self._request("GET", f"/api/v1/projects/download/{project_id}")
        flows: dict[str, bytes] = {}
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for name in zf.namelist():
                flows[name] = zf.read(name)
        return flows

    def upload_project(self, zip_bytes: bytes) -> list[Flow]:
        """Upload a project ZIP archive and return the created flows."""
        resp = self._request(
            "POST",
            "/api/v1/projects/upload/",
            content=zip_bytes,
            headers={"Content-Type": "application/octet-stream"},
        )
        return [Flow.model_validate(f) for f in resp.json()]

    # ------------------------------------------------------------------
    # File I/O helpers
    # ------------------------------------------------------------------

    def push(self, path: str | Path) -> tuple[Flow, bool]:
        """Upload or update a flow from a local JSON file.

        The ``id`` field embedded in the file is used for upsert
        (create-or-update via ``PUT /api/v1/flows/{id}``).
        Returns ``(flow, created)`` where ``created`` is ``True`` when the
        flow was newly created and ``False`` when it was updated::

            flow, created = client.push("flows/my-flow.json")
        """
        path = Path(path)
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        flow_id = data.get("id")
        if not flow_id:
            msg = f"Flow file {str(path)!r} does not contain an 'id' field; cannot upsert"
            raise ValueError(msg)
        flow_create = FlowCreate.model_validate({k: v for k, v in data.items() if k != "id"})
        return self.upsert_flow(flow_id, flow_create)

    def pull(
        self,
        flow_id: UUID | str,
        *,
        output: str | Path | None = None,
    ) -> dict[str, Any]:
        """Download a flow and return it as a normalized dict.

        Strips volatile fields (``updated_at``, ``user_id``, ...), clears
        secrets, and sorts keys for stable diffs.  When *output* is given the
        normalized JSON is also written to that file path::

            data = client.pull("my-flow-id")
            client.pull("my-flow-id", output="flows/my-flow.json")
        """
        flow = self.get_flow(flow_id)
        normalized = normalize_flow(flow.model_dump(mode="json"))
        if output is not None:
            out = Path(output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(flow_to_json(normalized), encoding="utf-8")
        return normalized

    def push_project(self, directory: str | Path) -> list[tuple[Flow, bool]]:
        """Push all ``*.json`` flow files in *directory* to the server.

        Each file is upserted using the ``id`` field it contains.
        Returns a list of ``(flow, created)`` pairs in the order files were
        processed::

            results = client.push_project("flows/my-project/")
            for flow, created in results:
                print("created" if created else "updated", flow.name)
        """
        directory = Path(directory)
        return [self.push(p) for p in sorted(directory.glob("*.json"))]

    def pull_project(
        self,
        project_id: UUID | str,
        *,
        output_dir: str | Path,
    ) -> dict[str, Path]:
        """Download all flows in a project and write them to *output_dir*.

        Each flow is normalized (volatile fields stripped, keys sorted) before
        being written as ``<flow-name>.json``.  *output_dir* is created if it
        does not exist.  Returns a mapping of ``{flow_name: file_path}``.

        .. note::
            If two flows in the project share the same name the second one
            overwrites the first on disk and in the returned mapping.  Flow
            names within a project should be unique; this situation indicates
            a data problem on the server.

        ::

            written = client.pull_project("project-id", output_dir="flows/")
            for name, path in written.items():
                print(name, "->", path)
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        raw_flows = self.download_project(project_id)  # {filename: bytes}
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

#: Short alias for :class:`LangflowClient`.
#:
#: Example::
#:
#:     from langflow_sdk import Client
#:     client = Client("https://langflow.example.com", api_key="...")
#:     flows  = client.list_flows()
#:     result = client.run_flow("my-endpoint", RunRequest(input_value="Hello"))
Client = LangflowClient

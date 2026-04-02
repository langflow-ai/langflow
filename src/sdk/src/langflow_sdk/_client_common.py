"""Shared helpers used by both sync and async Langflow SDK clients."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any, TypeVar

from langflow_sdk._http import _HTTP_201_CREATED, _logger
from langflow_sdk.models import FlowCreate, RunRequest, StreamChunk
from langflow_sdk.serialization import flow_to_json, normalize_flow

_ModelT = TypeVar("_ModelT")


class _ClientCommon:
    """Shared client helpers that are independent of sync vs async transport."""

    _MAX_ZIP_ENTRIES = 500
    _MAX_ENTRY_BYTES = 50 * 1024 * 1024  # 50 MB per file

    @staticmethod
    def _model_payload(model: Any) -> dict[str, Any]:
        """Return a JSON-safe payload for request models."""
        return model.model_dump(mode="json", exclude_none=True)

    @staticmethod
    def _validate_model(model_type: type[_ModelT], payload: Any) -> _ModelT:
        """Validate one SDK model from decoded JSON data."""
        return model_type.model_validate(payload)

    @classmethod
    def _validate_model_list(cls, model_type: type[_ModelT], payload: list[Any]) -> list[_ModelT]:
        """Validate a homogeneous SDK model list from decoded JSON data."""
        return [cls._validate_model(model_type, item) for item in payload]

    @staticmethod
    def _build_flow_list_params(
        *,
        folder_id: Any = None,
        remove_example_flows: bool,
        components_only: bool,
        get_all: bool,
        header_flows: bool,
        page: int,
        size: int,
    ) -> dict[str, Any]:
        """Build query parameters for the flows listing endpoints."""
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
        return params

    @classmethod
    def _build_run_request(
        cls,
        *,
        input_value: str,
        input_type: str,
        output_type: str,
        tweaks: dict[str, Any] | None,
        stream: bool = False,
    ) -> RunRequest:
        """Build a ``RunRequest`` shared by sync and async clients."""
        payload: dict[str, Any] = {
            "input_value": input_value,
            "input_type": input_type,
            "output_type": output_type,
            "tweaks": tweaks,
        }
        if stream:
            payload["stream"] = True
        return RunRequest(
            **payload,
        )

    @classmethod
    def _build_stream_payload(
        cls,
        *,
        input_value: str,
        input_type: str,
        output_type: str,
        tweaks: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build the POST body for streamed runs."""
        return cls._model_payload(
            cls._build_run_request(
                input_value=input_value,
                input_type=input_type,
                output_type=output_type,
                tweaks=tweaks,
                stream=True,
            )
        )

    @staticmethod
    def _extract_error_detail(body: bytes) -> str:
        """Extract a user-facing error detail from an HTTP error response body."""
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                return parsed.get("detail", body.decode(errors="replace"))
        except Exception:  # noqa: BLE001
            _logger.debug("Failed to parse error response body as JSON", exc_info=True)
        return body.decode(errors="replace")

    @staticmethod
    def _parse_stream_chunk(raw: str) -> StreamChunk | None:
        """Parse one NDJSON/SSE chunk, skipping malformed lines."""
        try:
            obj = json.loads(raw)
            return StreamChunk(event=obj["event"], data=obj.get("data", {}))
        except (json.JSONDecodeError, KeyError):
            _logger.debug("Skipping malformed SSE chunk", exc_info=True)
            return None

    @classmethod
    def _extract_project_archive(cls, content: bytes) -> dict[str, bytes]:
        """Read and validate the project ZIP payload returned by the API."""
        flows: dict[str, bytes] = {}
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            entries = zf.infolist()
            if len(entries) > cls._MAX_ZIP_ENTRIES:
                msg = f"ZIP contains {len(entries)} entries, exceeding the limit of {cls._MAX_ZIP_ENTRIES}"
                raise ValueError(msg)
            for info in entries:
                if info.file_size > cls._MAX_ENTRY_BYTES:
                    _logger.warning(
                        "Skipping ZIP entry %r: declared size %d exceeds limit",
                        info.filename,
                        info.file_size,
                    )
                    continue
                raw = zf.read(info.filename)
                if len(raw) > cls._MAX_ENTRY_BYTES:
                    _logger.warning("Skipping ZIP entry %r: actual size %d exceeds limit", info.filename, len(raw))
                    continue
                flows[info.filename] = raw
        return flows

    @staticmethod
    def _load_flow_file(path: str | Path) -> tuple[Any, FlowCreate]:
        """Load a flow file from disk and prepare it for upsert."""
        path = Path(path)
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        flow_id = data.get("id")
        if not flow_id:
            msg = f"Flow file {str(path)!r} does not contain an 'id' field; cannot upsert"
            raise ValueError(msg)
        flow_create = FlowCreate.model_validate({k: v for k, v in data.items() if k != "id"})
        return flow_id, flow_create

    @staticmethod
    def _normalize_flow_payload(payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize flow data for stable local serialization."""
        return normalize_flow(payload)

    @classmethod
    def _normalize_and_write_flow(
        cls,
        payload: dict[str, Any],
        *,
        output: str | Path | None = None,
    ) -> dict[str, Any]:
        """Normalize flow data and optionally persist it to disk."""
        normalized = cls._normalize_flow_payload(payload)
        if output is not None:
            out = Path(output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(flow_to_json(normalized), encoding="utf-8")
        return normalized

    @classmethod
    def _write_project_flows(
        cls,
        raw_flows: dict[str, bytes],
        *,
        output_dir: str | Path,
    ) -> dict[str, Path]:
        """Normalize and write a downloaded project archive to disk."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        written: dict[str, Path] = {}
        for filename, content in raw_flows.items():
            data: dict[str, Any] = json.loads(content.decode("utf-8"))
            normalized = cls._normalize_flow_payload(data)
            name = str(normalized.get("name") or Path(filename).stem)
            dest = out / f"{name}.json"
            dest.write_text(flow_to_json(normalized), encoding="utf-8")
            written[name] = dest
        return written

    @staticmethod
    def _project_json_paths(directory: str | Path) -> list[Path]:
        """Return sorted ``*.json`` paths within a project directory."""
        return sorted(Path(directory).glob("*.json"))

    @classmethod
    def _upsert_result(cls, model_type: type[_ModelT], response: Any) -> tuple[_ModelT, bool]:
        """Return ``(model, created)`` for an upsert response."""
        return cls._validate_model(model_type, response.json()), response.status_code == _HTTP_201_CREATED

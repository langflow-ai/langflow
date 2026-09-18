"""Bounded REST and MCP access to the public FXMacroData service."""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from dataclasses import dataclass, field
from importlib.resources import files
import json
import math
import os
import re
import socket
import threading
import time
from typing import Any, Iterator
from urllib.parse import quote

import jsonschema
from referencing import Registry
from referencing.exceptions import NoSuchResource, Unresolvable
import requests
from .transport import CredentialSafeAdapter, protected_diagnostics, redact_text

API_ORIGIN = "https://api.fxmacrodata.com"
MCP_URL = "https://mcp.fxmacrodata.com/mcp"
WEBSITE = "https://fxmacrodata.com"
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
MCP_PROTOCOL_VERSION = "2025-03-26"


def _no_remote_schema(uri: str) -> Any:
    """Input validation must never fetch a schema from another network origin."""
    raise NoSuchResource(ref=uri)


SCHEMA_REGISTRY = Registry(retrieve=_no_remote_schema)


class FXMacroDataError(RuntimeError):
    """An actionable error which never includes request URLs or credentials."""


@dataclass(frozen=True)
class Operation:
    name: str
    description: str
    input_schema: dict[str, Any]
    path: str
    method: str
    parameters: tuple[dict[str, Any], ...] = field(default_factory=tuple)


def list_operations(include_mcp: bool = True) -> tuple[Operation, ...]:
    """Return the complete packaged public operation inventory and input schemas."""
    raw = json.loads(files(__package__).joinpath("operations.json").read_text(encoding="utf-8"))
    operations = [Operation(**{**item, "parameters": tuple(item.get("parameters", []))}) for item in raw]
    if include_mcp:
        tools = json.loads(files(__package__).joinpath("mcp-tools.json").read_text(encoding="utf-8"))
        operations.extend(Operation("mcp_" + tool["name"], tool.get("description", tool["name"]), tool["inputSchema"], "/mcp", "MCP") for tool in tools)
    return tuple(operations)


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [deepcopy(row) if isinstance(row, dict) else {"value": deepcopy(row)} for row in payload]
    if not isinstance(payload, dict):
        return [] if payload is None else [{"value": deepcopy(payload)}]
    for key in ("structuredContent", "result", "data", "rows", "events", "announcements", "predictions", "prices", "commodities", "results", "series", "indicators"):
        if key in payload and isinstance(payload[key], (dict, list)):
            value = payload[key]
            if isinstance(value, dict) and value and all(isinstance(v, dict) for v in value.values()):
                return [{"record_key": k, "record": deepcopy(v)} for k, v in value.items()]
            return _records(value)
    # MCP text is rendered as text unless it contains a structured JSON result.
    if isinstance(payload.get("content"), list):
        rows = []
        for block in payload["content"]:
            if isinstance(block, dict) and block.get("type") == "text":
                try:
                    rows.extend(_records(json.loads(block["text"])))
                except (ValueError, KeyError):
                    rows.append({"text": block.get("text", "")})
            elif isinstance(block, dict):
                rows.append(deepcopy(block))
        return rows
    return [deepcopy(payload)] if payload else []


@dataclass(frozen=True)
class Result:
    """Original response plus an additive tabular view; no source fields renamed."""
    operation: str
    payload: Any
    source_url: str = WEBSITE

    def records(self) -> list[dict[str, Any]]:
        return _records(self.payload)

    def as_dict(self) -> dict[str, Any]:
        return {"operation": self.operation, "data": deepcopy(self.payload), "records": self.records(), "source_url": self.source_url}


class FXMacroDataClient:
    """Fixed-origin client with user-supplied authentication and safe errors.

    API keys belong in the constructor or FXMACRODATA_API_KEY / FXMD_API_KEY.
    They are never model-visible operation arguments. This client emits no telemetry.
    """

    def __init__(self, api_key: str | None = None, timeout: float = 30, *, session: requests.Session | None = None):
        if api_key is not None and not isinstance(api_key, str):
            raise FXMacroDataError("The optional API key must be a string.")
        try:
            timeout_value = float(timeout)
            if not math.isfinite(timeout_value):
                raise ValueError
        except (ValueError, TypeError, OverflowError):
            raise FXMacroDataError("The request timeout must be a finite number.") from None
        self._api_key = api_key if api_key is not None else (os.getenv("FXMACRODATA_API_KEY") or os.getenv("FXMD_API_KEY") or "")
        self.timeout = min(max(timeout_value, 1), 120)
        self._session = session or requests.Session()
        self._owns_session = session is None
        if self._owns_session:
            adapter = CredentialSafeAdapter()
            self._session.mount(API_ORIGIN + "/", adapter)
            self._session.mount("https://mcp.fxmacrodata.com/", adapter)
        self._operations = {operation.name: operation for operation in list_operations()}
        self._mcp_headers: dict[str, str] | None = None
        self._request_id = 0
        # requests.Session and MCP initialization both carry mutable state.
        # Serialize a shared client's calls; independent clients can run in parallel.
        self._lock = threading.RLock()

    def __repr__(self) -> str:
        return f"FXMacroDataClient(authenticated={bool(self._api_key)}, timeout={self.timeout})"

    def __enter__(self) -> FXMacroDataClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        with self._lock, protected_diagnostics(self._api_key):
            headers, self._mcp_headers = self._mcp_headers, None
            if headers and headers.get("Mcp-Session-Id"):
                response = None
                try:
                    response = self._request("DELETE", MCP_URL, params=self._auth_params(),
                                             headers=headers, timeout=min(self.timeout, 2))
                except Exception:
                    # Closing a session is best effort and must not mask a tool
                    # result or expose an underlying request/credential error.
                    pass
                finally:
                    if response is not None:
                        response.close()
            if self._owns_session:
                self._session.close()

    def list_operations(self, include_mcp: bool = True) -> tuple[Operation, ...]:
        with self._lock:
            return tuple(deepcopy(op) for op in self._operations.values() if include_mcp or op.method != "MCP")

    def _safe(self, value: Any) -> Any:
        if isinstance(value, str):
            return redact_text(value, self._api_key)
        if isinstance(value, list):
            return [self._safe(x) for x in value]
        if isinstance(value, dict):
            secret_fields = {"apikey", "accesstoken", "authorization", "proxyauthorization", "password", "clientsecret", "secret", "token"}
            return {self._safe(k): "[redacted]" if re.sub(r"[_-]", "", k.lower()) in secret_fields else self._safe(v) for k, v in value.items()}
        return value

    @staticmethod
    def _status(response: requests.Response) -> None:
        if 200 <= response.status_code < 300:
            return
        if response.status_code in {401, 403}:
            detail = "This dataset requires an authorized FXMacroData API key. Public USD catalogue, history and calendar remain available."
        elif response.status_code == 429:
            detail = "FXMacroData rate limit reached. Retry later."
        elif response.status_code == 404:
            detail = "The requested FXMacroData resource is unavailable. Check catalogue discovery."
        else:
            detail = f"FXMacroData request failed (HTTP {response.status_code})."
        raise FXMacroDataError(detail)

    def _request(self, method: str, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None, body: dict[str, Any] | None = None, timeout: float | None = None) -> requests.Response:
        try:
            with protected_diagnostics(self._api_key):
                return self._session.request(method, url, params=params, headers=headers, json=body, timeout=timeout or self.timeout, allow_redirects=False, stream=True)
        except (requests.RequestException, ValueError):
            raise FXMacroDataError("Unable to reach FXMacroData within the request timeout. Retry later.") from None

    def _bounded_lines(self, response: requests.Response, deadline: float, *, stop_at_deadline: bool = False) -> Iterator[bytes]:
        seen_bytes = 0
        pending = bytearray()
        skip_lf = False
        # iter_lines only yields after a delimiter, so a long undelimited frame
        # could evade both byte and elapsed-time checks. Bound raw bytes first.
        for chunk in response.iter_content(chunk_size=1):
            if not isinstance(chunk, bytes):
                raise FXMacroDataError("FXMacroData returned an invalid event stream.")
            seen_bytes += len(chunk)
            if seen_bytes > MAX_RESPONSE_BYTES:
                raise FXMacroDataError("FXMacroData response exceeded the bounded response budget.")
            if time.monotonic() > deadline:
                if stop_at_deadline:
                    return
                raise FXMacroDataError("FXMacroData response exceeded the bounded response budget.")
            for value in chunk:
                if skip_lf and value == 10:
                    skip_lf = False
                    continue
                skip_lf = value == 13
                if value in (10, 13):
                    yield bytes(pending)
                    pending.clear()
                else:
                    pending.append(value)

    @staticmethod
    @contextmanager
    def _response_deadline(response: requests.Response, deadline: float):
        """Interrupt this response's blocked read when its capture budget ends."""
        expired = threading.Event()

        def expire() -> None:
            expired.set()
            # Closing a buffered reader alone can wait on its active read lock.
            # Shut down only this response's socket first, which wakes that read.
            raw = getattr(response, "raw", None)
            connection = getattr(raw, "connection", None)
            sock = getattr(connection, "sock", None)
            if sock is None:
                fp = getattr(getattr(raw, "_fp", None), "fp", None)
                sock = getattr(getattr(fp, "raw", None), "_sock", None)
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except (OSError, ValueError):
                    pass
            try:
                response.close()
            except Exception:
                pass

        timer = threading.Timer(max(0, deadline - time.monotonic()), expire)
        timer.daemon = True
        timer.start()
        try:
            yield expired
        finally:
            timer.cancel()

    def _read_json(self, response: requests.Response, *, response_id: int | None = None) -> Any:
        try:
            self._status(response)
            deadline = time.monotonic() + self.timeout
            if "text/event-stream" in response.headers.get("Content-Type", "").lower():
                with self._response_deadline(response, deadline):
                    for event in self._parse_sse(self._bounded_lines(response, deadline)):
                        data = event["data"]
                        if (isinstance(data, dict) and data.get("jsonrpc") == "2.0"
                                and data.get("id") == response_id and ("result" in data or "error" in data)):
                            # Streamable HTTP may remain open after delivering this
                            # response. Do not wait for EOF or a later keepalive.
                            return data
                raise FXMacroDataError("FXMacroData returned no matching MCP response.")
            chunks = bytearray()
            with self._response_deadline(response, deadline):
                for chunk in response.iter_content(chunk_size=65536):
                    chunks.extend(chunk)
                    if len(chunks) > MAX_RESPONSE_BYTES or time.monotonic() > deadline:
                        raise FXMacroDataError("FXMacroData response exceeded the bounded response budget.")
            raw = chunks.decode("utf-8")
            return json.loads(raw)
        except (requests.RequestException, ValueError, UnicodeError, OSError, AttributeError):
            raise FXMacroDataError("FXMacroData returned an unavailable or invalid response.") from None
        finally:
            response.close()

    def _auth_params(self) -> dict[str, str]:
        return {"api_key": self._api_key} if self._api_key else {}

    def execute(self, operation_name: str, arguments: dict[str, Any] | None = None) -> Result:
        with self._lock, protected_diagnostics(self._api_key):
            return self._execute(operation_name, arguments)

    def _execute(self, operation_name: str, arguments: dict[str, Any] | None) -> Result:
        if not isinstance(operation_name, str):
            raise FXMacroDataError("Unknown FXMacroData operation. Use operation discovery.")
        op = self._operations.get(operation_name)
        if op is None:
            raise FXMacroDataError("Unknown FXMacroData operation. Use operation discovery.")
        if arguments is not None and (not isinstance(arguments, dict) or any(not isinstance(key, str) for key in arguments)):
            raise FXMacroDataError("FXMacroData arguments must be an object with string keys.")
        args = dict(arguments or {})
        if any(k.lower() in {"api_key", "access_token", "authorization", "url", "base_url"} for k in args):
            raise FXMacroDataError("Credentials and endpoint overrides are not operation arguments.")
        try:
            jsonschema.Draft202012Validator(op.input_schema, registry=SCHEMA_REGISTRY).validate(args)
        except (jsonschema.ValidationError, jsonschema.SchemaError, Unresolvable):
            raise FXMacroDataError("Invalid FXMacroData arguments. Check the operation input schema.") from None
        if op.method == "MCP":
            return self._call_mcp(op.name[4:], args)
        path = op.path
        params: dict[str, Any] = self._auth_params()
        headers = {"Accept": "application/json"}
        for parameter in op.parameters:
            name = parameter["name"]
            if name not in args or args[name] is None:
                continue
            value = args[name]
            if parameter["in"] == "path":
                if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]+", value) or value in {".", ".."}:
                    raise FXMacroDataError("Invalid FXMacroData path parameter.")
                path = path.replace("{" + name + "}", quote(value, safe=""))
            elif parameter["in"] == "header":
                if "\r" in str(value) or "\n" in str(value):
                    raise FXMacroDataError("Invalid event cursor.")
                headers[name] = str(value)
            else:
                params[name] = str(value).lower() if isinstance(value, bool) else value
        if operation_name == "stream_events":
            payload = self._stream(path, params, headers, args)
        else:
            payload = self._read_json(self._request("GET", API_ORIGIN + path, params=params, headers=headers))
        return Result(op.name, self._safe(payload), API_ORIGIN + path)

    @staticmethod
    def _parse_sse(lines: Any) -> Iterator[dict[str, Any]]:
        fields: dict[str, Any] = {}
        data: list[str] = []
        for raw in lines:
            line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            if line == "":
                if data:
                    text = "\n".join(data)
                    try:
                        fields["data"] = json.loads(text)
                    except ValueError:
                        fields["data"] = text
                    yield fields
                fields, data = {}, []
            elif not line.startswith(":"):
                key, _, value = line.partition(":")
                value = value.removeprefix(" ")
                if key == "data":
                    data.append(value)
                elif key in {"id", "event", "retry"}:
                    fields[key] = value
        # A connection ending before the blank event delimiter is incomplete;
        # do not turn a partial stream frame into a completed release event.

    def _stream(self, path: str, params: dict[str, Any], headers: dict[str, str], args: dict[str, Any]) -> dict[str, Any]:
        seconds = min(float(args.get("max_seconds", 10)), self.timeout)
        count = int(args.get("max_events", 10))
        deadline = time.monotonic() + seconds
        response = self._request("GET", API_ORIGIN + path, params=params, headers={**headers, "Accept": "text/event-stream"}, timeout=seconds)
        events = []
        expired = threading.Event()
        try:
            self._status(response)
            with self._response_deadline(response, deadline) as expired:
                for event in self._parse_sse(self._bounded_lines(response, deadline, stop_at_deadline=True)):
                    events.append(event)
                    if len(events) >= count:
                        break
        except (requests.RequestException, OSError):
            # A quiet stream can reach its finite read deadline without an event.
            return {"events": events, "capture_complete": False, "reason": "timeout"}
        except (UnicodeError, ValueError, TypeError, AttributeError):
            if expired.is_set():
                return {"events": events, "capture_complete": False, "reason": "timeout"}
            raise FXMacroDataError("FXMacroData returned an invalid event stream.") from None
        finally:
            response.close()
        return {"events": events, "capture_complete": len(events) >= count, "reason": "event_limit" if len(events) >= count else "timeout" if expired.is_set() else "stream_end_or_deadline"}

    def _rpc(self, method: str, params: dict[str, Any], *, headers: dict[str, str], notification: bool = False) -> tuple[Any, dict[str, str]]:
        body: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notification:
            self._request_id += 1
            body["id"] = self._request_id
        response = self._request("POST", MCP_URL, params=self._auth_params(), headers=headers, body=body)
        response_headers = dict(response.headers)
        if notification:
            try:
                self._status(response)
            finally:
                response.close()
            return None, response_headers
        value = self._read_json(response, response_id=body["id"])
        if (not isinstance(value, dict) or value.get("jsonrpc") != "2.0"
                or type(value.get("id")) is not int or value.get("id") != body["id"]
                or "error" in value or "result" not in value):
            raise FXMacroDataError("FXMacroData MCP could not complete this request.")
        return value["result"], response_headers

    def _initialize_mcp(self) -> dict[str, str]:
        if self._mcp_headers is None:
            headers = {"Accept": "application/json, text/event-stream"}
            result, returned = self._rpc("initialize", {"protocolVersion": MCP_PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "fxmacrodata-public-client", "version": "0.1.0"}}, headers=headers)
            if not isinstance(result, dict) or result.get("protocolVersion") != MCP_PROTOCOL_VERSION:
                raise FXMacroDataError("FXMacroData MCP returned an unsupported initialization response.")
            headers["MCP-Protocol-Version"] = MCP_PROTOCOL_VERSION
            for key, value in returned.items():
                if key.lower() == "mcp-session-id":
                    if not isinstance(value, str) or not re.fullmatch(r"[\x21-\x7e]+", value):
                        raise FXMacroDataError("FXMacroData MCP returned an invalid session header.")
                    headers["Mcp-Session-Id"] = value
            self._rpc("notifications/initialized", {}, headers=headers, notification=True)
            self._mcp_headers = headers
        return self._mcp_headers

    def discover_mcp_tools(self) -> tuple[Operation, ...]:
        """Refresh every advertised hosted MCP tool, including paginated discovery."""
        with self._lock, protected_diagnostics(self._api_key):
            return self._discover_mcp_tools()

    def _discover_mcp_tools(self) -> tuple[Operation, ...]:
        headers = self._initialize_mcp()
        cursor = None
        seen: set[str] = set()
        discovered = []
        deadline = time.monotonic() + self.timeout
        while True:
            result, _ = self._rpc("tools/list", {"cursor": cursor} if cursor else {}, headers=headers)
            if not isinstance(result, dict) or not isinstance(result.get("tools"), list):
                raise FXMacroDataError("FXMacroData MCP returned an invalid tool catalogue.")
            for tool in result["tools"]:
                if (not isinstance(tool, dict) or not isinstance(tool.get("name"), str)
                        or not isinstance(tool.get("inputSchema"), dict)):
                    raise FXMacroDataError("FXMacroData MCP returned an invalid tool descriptor.")
                try:
                    jsonschema.Draft202012Validator.check_schema(tool["inputSchema"])
                except jsonschema.SchemaError:
                    raise FXMacroDataError("FXMacroData MCP returned an invalid tool schema.") from None
                op = Operation("mcp_" + tool["name"], tool.get("description", tool["name"]), tool["inputSchema"], "/mcp", "MCP")
                discovered.append(op)
            cursor = result.get("nextCursor")
            if not cursor:
                break
            if not isinstance(cursor, str):
                raise FXMacroDataError("FXMacroData MCP returned an invalid page cursor.")
            if cursor in seen:
                raise FXMacroDataError("FXMacroData MCP discovery returned a repeated page cursor.")
            if len(seen) >= 100 or len(discovered) > 10000 or time.monotonic() > deadline:
                raise FXMacroDataError("FXMacroData MCP discovery exceeded its bounded response budget.")
            seen.add(cursor)
        # A failed page never partially mutates the usable operation catalogue.
        self._operations.update({operation.name: operation for operation in discovered})
        return tuple(discovered)

    def _call_mcp(self, name: str, args: dict[str, Any]) -> Result:
        result, _ = self._rpc("tools/call", {"name": name, "arguments": args}, headers=self._initialize_mcp())
        if not isinstance(result, dict) or result.get("isError"):
            raise FXMacroDataError("FXMacroData MCP tool is unavailable. Check arguments and dataset access.")
        return Result("mcp_" + name, self._safe(result), WEBSITE)

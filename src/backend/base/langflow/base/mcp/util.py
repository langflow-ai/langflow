import asyncio
import contextlib
import os
import platform
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from typing import Any, cast
from urllib.parse import urlparse
from uuid import UUID

import aiofiles
import httpx
from anyio import Path
from httpx import codes as httpx_codes
from loguru import logger
from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.client.sse import sse_client
from pydantic import BaseModel, Field, create_model
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow

HTTP_ERROR_STATUS_CODE = httpx_codes.BAD_REQUEST  # HTTP status code for client errors
NULLABLE_TYPE_LENGTH = 2  # Number of types in a nullable union (the type itself + null)


def create_tool_coroutine(tool_name: str, arg_schema: type[BaseModel], session) -> Callable[..., Awaitable]:
    async def tool_coroutine(*args, **kwargs):
        # Get field names from the model (preserving order)
        field_names = list(arg_schema.__fields__.keys())
        provided_args = {}
        # Map positional arguments to their corresponding field names
        for i, arg in enumerate(args):
            if i >= len(field_names):
                msg = "Too many positional arguments provided"
                raise ValueError(msg)
            provided_args[field_names[i]] = arg
        # Merge in keyword arguments
        provided_args.update(kwargs)
        # Validate input and fill defaults for missing optional fields
        try:
            validated = arg_schema.parse_obj(provided_args)
        except Exception as e:
            msg = f"Invalid input: {e}"
            raise ValueError(msg) from e
        return await session.call_tool(tool_name, arguments=validated.dict())

    return tool_coroutine


def create_tool_func(tool_name: str, arg_schema: type[BaseModel], session) -> Callable[..., str]:
    def tool_func(*args, **kwargs):
        field_names = list(arg_schema.__fields__.keys())
        provided_args = {}
        for i, arg in enumerate(args):
            if i >= len(field_names):
                msg = "Too many positional arguments provided"
                raise ValueError(msg)
            provided_args[field_names[i]] = arg
        provided_args.update(kwargs)
        try:
            validated = arg_schema.parse_obj(provided_args)
        except Exception as e:
            msg = f"Invalid input: {e}"
            raise ValueError(msg) from e
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(session.call_tool(tool_name, arguments=validated.dict()))

    return tool_func


async def get_flow_snake_case(flow_name: str, user_id: str, session, is_action: bool | None = None) -> Flow | None:
    uuid_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
    stmt = select(Flow).where(Flow.user_id == uuid_user_id).where(Flow.is_component == False)  # noqa: E712
    flows = (await session.exec(stmt)).all()

    for flow in flows:
        this_flow_name = flow.action_name if is_action and flow.action_name else "_".join(flow.name.lower().split())
        if this_flow_name == flow_name:
            return flow
    return None


def create_input_schema_from_json_schema(schema: dict[str, Any]) -> type[BaseModel]:
    """Dynamically build a Pydantic model from a JSON schema (with $defs).

    Non-required fields become Optional[...] with default=None.
    """
    if schema.get("type") != "object":
        msg = "Root schema must be type 'object'"
        raise ValueError(msg)

    defs: dict[str, dict[str, Any]] = schema.get("$defs", {})
    model_cache: dict[str, type[BaseModel]] = {}

    def resolve_ref(s: dict[str, Any] | None) -> dict[str, Any]:
        """Follow a $ref chain until you land on a real subschema."""
        if s is None:
            return {}
        while "$ref" in s:
            ref_name = s["$ref"].split("/")[-1]
            s = defs.get(ref_name)
            if s is None:
                logger.warning(f"Parsing input schema: Definition '{ref_name}' not found")
                return {"type": "string"}
        return s

    def parse_type(s: dict[str, Any] | None) -> Any:
        """Map a JSON Schema subschema to a Python type (possibly nested)."""
        if s is None:
            return None
        s = resolve_ref(s)

        if "anyOf" in s:
            # Handle common pattern for nullable types (anyOf with string and null)
            subtypes = [sub.get("type") for sub in s["anyOf"] if isinstance(sub, dict) and "type" in sub]

            # Check if this is a simple nullable type (e.g., str | None)
            if len(subtypes) == NULLABLE_TYPE_LENGTH and "null" in subtypes:
                # Get the non-null type
                non_null_type = next(t for t in subtypes if t != "null")
                # Map it to Python type
                if isinstance(non_null_type, str):
                    return {
                        "string": str,
                        "integer": int,
                        "number": float,
                        "boolean": bool,
                        "object": dict,
                        "array": list,
                    }.get(non_null_type, Any)
                return Any

            # For other anyOf cases, use the first non-null type
            subtypes = [parse_type(sub) for sub in s["anyOf"]]
            non_null_types = [t for t in subtypes if t is not None and t is not type(None)]
            if non_null_types:
                return non_null_types[0]
            return str

        t = s.get("type", "any")  # Use string "any" as default instead of Any type
        if t == "array":
            item_schema = s.get("items", {})
            schema_type: Any = parse_type(item_schema)
            return list[schema_type]

        if t == "object":
            # inline object not in $defs ⇒ anonymous nested model
            return _build_model(f"AnonModel{len(model_cache)}", s)

        # primitive fallback
        return {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "object": dict,
            "array": list,
        }.get(t, Any)

    def _build_model(name: str, subschema: dict[str, Any]) -> type[BaseModel]:
        """Create (or fetch) a BaseModel subclass for the given object schema."""
        # If this came via a named $ref, use that name
        if "$ref" in subschema:
            refname = subschema["$ref"].split("/")[-1]
            if refname in model_cache:
                return model_cache[refname]
            target = defs.get(refname)
            if not target:
                msg = f"Definition '{refname}' not found"
                raise ValueError(msg)
            cls = _build_model(refname, target)
            model_cache[refname] = cls
            return cls

        # Named anonymous or inline: avoid clashes by name
        if name in model_cache:
            return model_cache[name]

        props = subschema.get("properties", {})
        reqs = set(subschema.get("required", []))
        fields: dict[str, Any] = {}

        for prop_name, prop_schema in props.items():
            py_type = parse_type(prop_schema)
            is_required = prop_name in reqs
            if not is_required:
                py_type = py_type | None
                default = prop_schema.get("default", None)
            else:
                default = ...  # required by Pydantic

            fields[prop_name] = (py_type, Field(default, description=prop_schema.get("description")))

        model_cls = create_model(name, **fields)
        model_cache[name] = model_cls
        return model_cls

    # build the top - level "InputSchema" from the root properties
    top_props = schema.get("properties", {})
    top_reqs = set(schema.get("required", []))
    top_fields: dict[str, Any] = {}

    for fname, fdef in top_props.items():
        py_type = parse_type(fdef)
        if fname not in top_reqs:
            py_type = py_type | None
            default = fdef.get("default", None)
        else:
            default = ...
        top_fields[fname] = (py_type, Field(default, description=fdef.get("description")))

    return create_model("InputSchema", **top_fields)


class MCPStdioClient:
    def __init__(self):
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()
        self.max_retries = 1
        self.retry_delay = 1.0  # seconds
        self.timeout_seconds = 30  # default timeout

    async def connect_to_server(self, command_str: str, env: list[str] | None = None):
        env_dict: dict[str, str] = {}
        if env is None:
            env = []
        for var in env:
            if "=" not in var:
                msg = f"Invalid env var format: {var}. Must be in the format 'VAR_NAME=VAR_VALUE'"
                raise ValueError(msg)
            env_dict[var.split("=")[0]] = var.split("=")[1]
        command = command_str.split(" ")
        server_params = None
        env_data: dict[str, str] = {"DEBUG": "true", "PATH": os.environ["PATH"], **(env_dict or {})}

        # Create platform-specific command wrapper
        if platform.system() == "Windows":
            # For Windows, use cmd.exe with error reporting
            server_params = StdioServerParameters(
                command="cmd",
                args=[
                    "/c",
                    f"{command[0]} {' '.join(command[1:])} || echo Command failed with exit code %errorlevel% 1>&2",
                ],
                env=env_data,
            )
        else:
            # For Unix-like systems, use bash with error reporting
            server_params = StdioServerParameters(
                command="bash",
                args=["-c", f"{command_str} || echo 'Command failed with exit code $?' >&2"],
                env=env_data,
            )

        # Create a temporary file to capture stderr
        errlog_path = ""
        async with aiofiles.tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", delete=False) as tmp:
            errlog_path = cast(str, tmp.name)

            try:
                # Pass the temp file as errlog to capture stderr
                stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params, errlog=tmp))
                self.stdio, self.write = stdio_transport
                self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

                # Create a watcher task to monitor stderr
                async def watch_stderr():
                    last_size = 0
                    full_log = ""
                    while True:
                        await asyncio.sleep(0.05)
                        await tmp.flush()
                        current = (await Path(errlog_path).stat()).st_size
                        if current > last_size:
                            async with aiofiles.open(errlog_path, encoding="utf-8") as f:
                                await f.seek(last_size)
                                data = await f.read()
                                full_log += data
                                data = data.strip()

                            # Check for our specific error message pattern
                            if "Command failed with exit code" in data:
                                msg = f"MCP server command failed: {command_str}\nFull error log:\n{full_log}"
                                raise RuntimeError(msg)
                        last_size = current

                # Create tasks for both operations
                watcher = asyncio.create_task(watch_stderr())
                initializer = asyncio.create_task(self.session.initialize())

                # Race them: first to finish wins
                done, pending = await asyncio.wait({watcher, initializer}, return_when=asyncio.FIRST_COMPLETED)

                if watcher in done:
                    # stderr watcher fired → cancel and propagate its error
                    initializer.cancel()
                    watcher.result()  # This will re-raise the RuntimeError
                else:
                    # initialize succeeded → cancel watcher
                    watcher.cancel()
                    initializer.result()  # Will re-raise any initialization errors

                # If we get here, initialization succeeded
                response = await self.session.list_tools()
                # return response.tools

            except FileNotFoundError as e:
                # Command not found, raise immediately
                msg = f"Command not found: {command[0]}. Error: {e}"
                raise ValueError(msg) from e
            except OSError as e:
                # Other OS errors (e.g., permission denied)
                msg = f"Failed to start command '{command[0]}': {e}"
                raise ValueError(msg) from e
            except RuntimeError as e:
                # This is from our stderr watcher
                msg = f"MCP server error: {e}"
                raise ConnectionError(msg) from e
            except Exception as e:
                msg = f"Failed to initialize MCP session: {e}"
                logger.warning(msg)
                raise ConnectionError(msg) from e
            else:
                return response.tools
            finally:
                # Clean up the temp file
                with contextlib.suppress(FileNotFoundError, PermissionError):
                    await Path(errlog_path).unlink()


class MCPSseClient:
    def __init__(self):
        self.write = None
        self.sse = None
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds

    async def validate_url(self, url: str | None) -> tuple[bool, str]:
        """Validate the SSE URL before attempting connection."""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False, "Invalid URL format. Must include scheme (http/https) and host."

            async with httpx.AsyncClient() as client:
                try:
                    # First try a HEAD request to check if server is reachable
                    response = await client.head(url, timeout=5.0)
                    if response.status_code >= HTTP_ERROR_STATUS_CODE:
                        return False, f"Server returned error status: {response.status_code}"

                except httpx.TimeoutException:
                    return False, "Connection timed out. Server may be down or unreachable."
                except httpx.NetworkError:
                    return False, "Network error. Could not reach the server."
                else:
                    return True, ""

        except (httpx.HTTPError, ValueError, OSError) as e:
            return False, f"URL validation error: {e!s}"

    async def pre_check_redirect(self, url: str | None) -> str | None:
        """Check for redirects and return the final URL."""
        if url is None:
            return url
        try:
            async with httpx.AsyncClient(follow_redirects=False) as client:
                response = await client.request("HEAD", url)
                if response.status_code == httpx.codes.TEMPORARY_REDIRECT:
                    return response.headers.get("Location", url)
        except (httpx.RequestError, httpx.HTTPError) as e:
            logger.warning(f"Error checking redirects: {e}")
        return url

    async def _connect_with_timeout(
        self, url: str | None, headers: dict[str, str] | None, timeout_seconds: int, sse_read_timeout_seconds: int
    ):
        """Attempt to connect with timeout."""
        try:
            if url is None:
                return
            sse_transport = await self.exit_stack.enter_async_context(
                sse_client(url, headers, timeout_seconds, sse_read_timeout_seconds)
            )
            self.sse, self.write = sse_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.sse, self.write))
            await self.session.initialize()
        except Exception as e:
            msg = f"Failed to establish SSE connection: {e!s}"
            raise ConnectionError(msg) from e

    async def connect_to_server(
        self,
        url: str | None,
        headers: dict[str, str] | None,
        timeout_seconds: int = 30,
        sse_read_timeout_seconds: int = 30,
    ):
        """Connect to server with retries and improved error handling."""
        if headers is None:
            headers = {}

        # First validate the URL
        is_valid, error_msg = await self.validate_url(url)
        if not is_valid:
            msg = f"Invalid SSE URL ({url}): {error_msg}"
            raise ValueError(msg)

        url = await self.pre_check_redirect(url)
        last_error = None

        for attempt in range(self.max_retries):
            try:
                await asyncio.wait_for(
                    self._connect_with_timeout(url, headers, timeout_seconds, sse_read_timeout_seconds),
                    timeout=timeout_seconds,
                )

                if self.session is None:
                    msg = "Session not initialized"
                    raise ValueError(msg)

                response = await self.session.list_tools()

            except asyncio.TimeoutError:
                last_error = f"Connection to {url} timed out after {timeout_seconds} seconds"
                logger.warning(f"Connection attempt {attempt + 1} failed: {last_error}")
            except ConnectionError as err:
                last_error = str(err)
                logger.warning(f"Connection attempt {attempt + 1} failed: {last_error}")
            except (ValueError, httpx.HTTPError, OSError) as err:
                last_error = f"Connection error: {err!s}"
                logger.warning(f"Connection attempt {attempt + 1} failed: {last_error}")
            else:
                return response.tools

            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))

        msg = f"Failed to connect after {self.max_retries} attempts. Last error: {last_error}"
        raise ConnectionError(msg)

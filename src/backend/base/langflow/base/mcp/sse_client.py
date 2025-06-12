import asyncio
import json
from contextlib import AsyncExitStack, suppress
from typing import Any
from urllib.parse import urlparse

import httpx
from httpx import HTTPStatusError
from httpx import codes as httpx_codes
from langchain_core.tools import StructuredTool
from loguru import logger

# Core SDK re-exports
from mcp import ClientSession, types

# SSE helper from core SDK
from langflow.utils.version import get_version_info

HTTP_ERROR_STATUS_CODE = httpx_codes.BAD_REQUEST  # HTTP status code for client errors

# Constants for magic numbers
HTTP_STATUS_OK = 200
HTTP_STATUS_NOT_FOUND = 404
HTTP_STATUS_SERVER_ERROR = 500


class MCPConnectionError(Exception):
    """Custom exception for MCP connection errors."""


class MCPTransportError(Exception):
    """Custom exception for MCP transport errors."""


class MCPSseClient:
    """MCP SSE Client with support for multiple transport protocols.

    Supports:
    - Streamable HTTP transport (MCP 2025-03-26)
    - HTTP+SSE dual-endpoint transport (MCP 2024-11-05)

    Features enhanced retry logic, timeout controls, and transport detection.
    """

    def __init__(self) -> None:
        self.sse = None
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()

        # Enhanced retry configuration
        self.max_retries = 3
        self.base_retry_delay = 1.0  # seconds - base delay for exponential backoff
        self.max_retry_delay = 10.0  # seconds - maximum delay between retries
        self.retry_exponential_base = 2  # exponential backoff multiplier

        # More granular timeout controls
        self.default_connect_timeout = 30  # default connection timeout
        self.discovery_timeout = 15  # endpoint discovery timeout
        self.handshake_timeout = 10  # initialization handshake timeout
        self.request_timeout = 30  # individual request timeout

        # Transport tracking
        self.connected_transport: str | None = None  # Track which transport was successfully used
        self.discovery_task: asyncio.Task | None = None  # Background task for session maintenance
        self.discovered_endpoint: str | None = None  # Store discovered endpoint URL
        self.response_futures: dict[str, asyncio.Future[dict]] = {}  # Track pending requests
        self.request_id_counter = 0  # Generate unique request IDs

        # Store the result of the `initialize` handshake when using HTTP+SSE
        self.init_result: types.InitializeResult | None = None

        # Get the project version
        self._version = get_version_info()["version"]

        # Compatibility fields for existing API
        self._connection_params: dict[str, Any] | None = None
        self._connected = False

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay for retry attempts."""
        delay = self.base_retry_delay * (self.retry_exponential_base**attempt)
        return min(delay, self.max_retry_delay)

    async def validate_url(self, url: str | None) -> tuple[bool, str]:
        """Validate the URL format before attempting connection."""
        try:
            if not url:
                return False, "URL is required"

            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False, "Invalid URL format. Must include scheme (http/https) and host."

            if parsed.scheme not in ["http", "https"]:
                return False, "URL must use http or https scheme"

        except (ValueError, AttributeError, TypeError) as e:
            return False, f"URL validation error: {e}"

        return True, ""

    async def pre_check_redirect(self, url: str | None) -> str | None:
        """Check for redirects and return the final URL."""
        if url is None:
            return url
        try:
            async with httpx.AsyncClient(follow_redirects=False, timeout=5.0) as client:
                response = await client.head(url)
                if response.status_code == httpx.codes.TEMPORARY_REDIRECT:
                    return response.headers.get("Location", url)
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as e:
            logger.debug(f"Error checking redirects for {url}: {e}")
        return url

    async def _try_streamable_http_transport(
        self, url: str, headers: dict[str, str] | None, timeout_seconds: int = 15
    ) -> Any:
        """Try to connect using Streamable HTTP transport (MCP 2025-03-26)."""
        logger.debug(f"Attempting Streamable HTTP transport (MCP 2025-03-26) at {url}")

        try:
            from contextlib import asynccontextmanager
            from datetime import timedelta

            from mcp.client.streamable_http import streamablehttp_client  # type: ignore[import-untyped]

            merged_headers = {"Accept": "application/json, text/event-stream", **(headers or {})}

            @asynccontextmanager
            async def _session_cm():
                async with (
                    streamablehttp_client(
                        url,
                        headers=merged_headers,
                        timeout=timedelta(seconds=timeout_seconds),
                    ) as (read_stream, write_stream, _get_session_id),
                    ClientSession(read_stream, write_stream) as session,
                ):
                    logger.debug("Initializing Streamable HTTP session...")
                    async with asyncio.timeout(self.handshake_timeout):
                        await session.initialize()
                    logger.debug("Streamable HTTP session initialized successfully")
                    yield session

            logger.info(f"Successfully connected using Streamable HTTP transport at {url}")
            return _session_cm()

        except ImportError:
            logger.debug("streamablehttp_client helper not available - skipping Streamable HTTP transport.")
            return None
        except asyncio.TimeoutError:
            logger.debug(f"Streamable HTTP transport timed out during handshake at {url}")
            return None
        except (ConnectionError, OSError, httpx.HTTPError) as exc:
            logger.debug(f"Streamable HTTP transport failed at {url}: {exc}")
            return None

    async def _mcp_http_sse_discovery_handler(
        self, url: str, headers: dict[str, str] | None, endpoint_queue: asyncio.Queue[tuple[str, str | dict]]
    ):
        """Handle MCP 2024-11-05 HTTP+SSE backward compatibility pattern."""
        try:
            logger.debug(f"Starting MCP HTTP+SSE discovery and response handler for {url}")

            request_headers = {"Accept": "application/json, text/event-stream", **(headers or {})}

            async with (
                httpx.AsyncClient(timeout=60) as client,
                client.stream("GET", url, headers=request_headers) as response,
            ):
                if response.status_code != HTTP_STATUS_OK:
                    error_msg = f"HTTP+SSE discovery failed with status {response.status_code}"
                    if response.status_code == HTTP_STATUS_NOT_FOUND:
                        error_msg += f" - Endpoint not found: {url}"
                    elif response.status_code >= HTTP_STATUS_SERVER_ERROR:
                        error_msg += f" - Server error at {url}"
                    await endpoint_queue.put(("error", error_msg))
                    return

                content_type = response.headers.get("content-type", "")
                if "text/event-stream" not in content_type.lower():
                    await endpoint_queue.put(("error", f"Expected SSE stream but got content-type: {content_type}"))
                    return

                logger.debug("MCP HTTP+SSE discovery session established, monitoring for events...")
                endpoint_discovered = False

                async for chunk in response.aiter_text():
                    if not chunk.strip():
                        continue

                    lines = chunk.strip().split("\n")
                    event_type = None
                    event_data_lines = []

                    # Process SSE lines following spec: collect all data lines for multi-line support
                    for line in lines:
                        if line.startswith("event:"):
                            event_type = line[6:].strip()
                        elif line.startswith("data:"):
                            event_data_lines.append(line[5:].strip())

                    # Join all data lines for complete event data (handles multi-line data per SSE spec)
                    event_data = "\n".join(event_data_lines) if event_data_lines else None

                    if event_type == "endpoint" and event_data and not endpoint_discovered:
                        await endpoint_queue.put(("endpoint", event_data))
                        endpoint_discovered = True

                    elif event_type == "message" and event_data:
                        try:
                            response_json = json.loads(event_data)
                            await endpoint_queue.put(("response", response_json))
                        except json.JSONDecodeError as e:
                            logger.warning(f"Invalid JSON in SSE message: {e}")

        except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
            await endpoint_queue.put(("error", f"HTTP+SSE discovery handler error: {e}"))

    async def _mcp_http_sse_send_request(self, request_data: dict) -> dict:
        """Send a request via HTTP+SSE pattern and wait for response."""
        if not self.discovered_endpoint:
            msg = "No discovered endpoint for HTTP+SSE requests"
            raise RuntimeError(msg)

        request_id = str(self.request_id_counter)
        self.request_id_counter += 1

        request_data["id"] = request_id

        future: asyncio.Future[dict] = asyncio.Future()
        self.response_futures[request_id] = future

        try:
            async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                response = await client.post(
                    self.discovered_endpoint,
                    json=request_data,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code != HTTP_STATUS_OK:
                    # Include response context in error message for better debugging
                    response_text = ""
                    try:
                        response_text = response.text[:200]  # Limit to first 200 chars
                    except (AttributeError, UnicodeDecodeError, ValueError):
                        response_text = "<unable to read response text>"
                    msg = f"HTTP {response.status_code}: {response_text}"
                    raise HTTPStatusError(msg, request=None, response=response)

            # Wait for the response via SSE
            return await asyncio.wait_for(future, timeout=self.request_timeout)

        except asyncio.TimeoutError as exc:
            msg = f"Request {request_id} timed out"
            raise TimeoutError(msg) from exc
        finally:
            self.response_futures.pop(request_id, None)

    async def _try_http_sse_transport(
        self,
        url: str,
        headers: dict[str, str] | None,
        _timeout_seconds: int,  # Unused but kept for API compatibility
    ) -> bool:
        """Try to connect using HTTP+SSE transport (MCP 2024-11-05)."""
        logger.debug(f"Attempting HTTP+SSE transport (MCP 2024-11-05) at {url}")

        endpoint_queue: asyncio.Queue[tuple[str, str | dict]] = asyncio.Queue()
        discovery_task = None

        try:
            discovery_task = asyncio.create_task(self._mcp_http_sse_discovery_handler(url, headers, endpoint_queue))

            # Wait for either endpoint discovery or error
            async with asyncio.timeout(self.discovery_timeout):
                event_type, event_data = await endpoint_queue.get()

            if event_type == "error":
                logger.debug(f"HTTP+SSE transport failed: {event_data}")
                return False
            if event_type == "endpoint":
                # event_data should be a string for endpoint events
                if isinstance(event_data, str):
                    self.discovered_endpoint = event_data
                    logger.debug(f"Discovered HTTP+SSE endpoint: {event_data}")
                else:
                    logger.warning(f"Expected string for endpoint event, got {type(event_data)}: {event_data}")
                    return False

                # Set up response handler task
                self.discovery_task = discovery_task

                # Perform initialization handshake
                init_request = {
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": self._get_initialize_request_params("2024-11-05"),
                }

                init_response = await self._mcp_http_sse_send_request(init_request)

                if "result" in init_response:
                    self.init_result = types.InitializeResult(**init_response["result"])
                    logger.info(f"Successfully connected using HTTP+SSE transport at {url}")
                    return True
                logger.debug("HTTP+SSE initialization failed: no result in response")
                return False
            return False  # noqa: TRY300

        except asyncio.TimeoutError:
            logger.debug(f"HTTP+SSE transport discovery timed out at {url}")
            return False
        except (ConnectionError, OSError, httpx.HTTPError) as exc:
            logger.debug(f"HTTP+SSE transport failed at {url}: {exc}")
            return False
        finally:
            if discovery_task and not self.discovery_task:
                discovery_task.cancel()
                with suppress(asyncio.CancelledError):
                    await discovery_task

    async def connect_to_server_with_retry(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout_seconds: int = 30,
        sse_read_timeout_seconds: int = 30,
        max_retries: int | None = None,
    ):
        """Connect with retry logic and exponential backoff."""
        if max_retries is None:
            max_retries = self.max_retries

        is_valid, error_msg = await self.validate_url(url)
        if not is_valid:
            msg = f"Invalid URL: {error_msg}"
            raise ValueError(msg)

        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                return await self.connect_to_server(url, headers, timeout_seconds, sse_read_timeout_seconds)
            except (ConnectionError, OSError, httpx.HTTPError, asyncio.TimeoutError) as e:
                last_exception = e
                if attempt < max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    logger.debug(f"Connection attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Max retries ({max_retries}) exceeded for {url}")

        msg = f"Max retries exceeded. Last error: {last_exception}"
        raise MCPConnectionError(msg)

    async def connect_to_server(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout_seconds: int = 30,
        _sse_read_timeout_seconds: int = 30,  # Unused but kept for API compatibility
    ) -> list[StructuredTool]:
        """Connect to MCP server with transport detection and fallback."""
        is_valid, error_msg = await self.validate_url(url)
        if not is_valid:
            msg = f"Invalid URL: {error_msg}"
            raise ValueError(msg)

        url = await self.pre_check_redirect(url) or url

        # Phase 1: Try Streamable HTTP (MCP 2025-03-26)
        logger.debug("Phase 1: Attempting Streamable HTTP transport")
        streamable_session_cm = await self._try_streamable_http_transport(url, headers, timeout_seconds)

        if streamable_session_cm is not None:
            self.session = await self.exit_stack.enter_async_context(streamable_session_cm)
            self.connected_transport = "streamable_http"
            self._connected = True

            # Get tools from session
            if self.session is None:
                msg = "Session is None after successful initialization"
                raise RuntimeError(msg)
            response = await self.session.list_tools()
            tools_list = self._normalize_tools(response.tools)
            logger.info(f"Successfully connected via Streamable HTTP, found {len(tools_list)} tools")
            return tools_list

        # Phase 2: Try HTTP+SSE (MCP 2024-11-05)
        logger.debug("Phase 2: Attempting HTTP+SSE transport")
        http_sse_success = await self._try_http_sse_transport(url, headers, timeout_seconds)

        if http_sse_success:
            self.connected_transport = "http_sse"
            self._connected = True

            # Get tools via HTTP+SSE
            tools_request = {"jsonrpc": "2.0", "method": "tools/list"}
            tools_response = await self._mcp_http_sse_send_request(tools_request)

            if "result" in tools_response and "tools" in tools_response["result"]:
                raw_tools = tools_response["result"]["tools"]
                tools_list = self._normalize_tools([types.Tool(**tool) for tool in raw_tools])
                logger.info(f"Successfully connected via HTTP+SSE, found {len(tools_list)} tools")
                return tools_list

        # Phase 3: Both transports failed
        error_msg = (
            f"Both transport methods failed for {url}. Tried: Streamable HTTP (2025-03-26), HTTP+SSE (2024-11-05)"
        )
        logger.error(error_msg)
        raise MCPTransportError(error_msg)

    async def list_tools(self) -> list[StructuredTool]:
        """Return the list of available tools depending on the active transport."""
        if self.connected_transport == "http_sse":
            if self.discovered_endpoint is None:
                msg = "HTTP+SSE session has no discovered endpoint"
                raise RuntimeError(msg)

            tools_request = {"jsonrpc": "2.0", "method": "tools/list"}
            try:
                tools_response = await self._mcp_http_sse_send_request(tools_request)
            except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as exc:
                logger.error(f"Failed to list tools via HTTP+SSE transport: {exc}")
                return []

            if "result" in tools_response and "tools" in tools_response["result"]:
                tool_dicts = tools_response["result"]["tools"]
                tool_objects: list[types.Tool] = []
                for tool in tool_dicts:
                    if not isinstance(tool, dict) or "name" not in tool:
                        logger.warning(f"Skipping invalid tool definition: {tool}")
                        continue
                    try:
                        tool_objects.append(
                            types.Tool(
                                name=tool["name"],
                                description=tool.get("description", ""),
                                inputSchema=tool.get("inputSchema", {}),
                            )
                        )
                    except (ValueError, TypeError) as exc:
                        logger.warning(f"Error parsing tool '{tool}': {exc}")

                return self._normalize_tools(tool_objects)

            logger.warning("HTTP+SSE server responded to tools/list but returned no tools")
            return []

        # Modern transports - delegate to the active session
        if self.connected_transport == "streamable_http" and self.session is not None:
            try:
                async with asyncio.timeout(10):
                    response = await self.session.list_tools()
            except asyncio.TimeoutError:
                logger.warning(f"Tool listing timed out after 10s via {self.connected_transport}")
                return []
            except (asyncio.CancelledError, Exception) as exc:
                logger.debug(f"list_tools() failed via active transport '{self.connected_transport}': {exc}")
                return []

            if hasattr(response, "tools"):
                raw_tools = response.tools
            elif isinstance(response, dict) and "tools" in response:
                raw_tools = response["tools"]
            else:
                raw_tools = response

            return self._normalize_tools(raw_tools)

        # No transport active
        msg = "Not connected to any transport. Call connect_to_server() first."
        raise RuntimeError(msg)

    async def call_tool(self, name: str, arguments: dict):
        """Call a tool using the active transport."""
        if self.connected_transport == "http_sse":
            request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
            return await self._mcp_http_sse_send_request(request)
        if self.connected_transport == "streamable_http" and self.session:
            return await self.session.call_tool(name, arguments=arguments)
        msg = "Not connected to any transport"
        raise RuntimeError(msg)

    async def run_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Run a tool with the given arguments.

        Compatibility method for existing Langflow integration.
        """
        if not self._connected:
            msg = "Session not initialized or disconnected. Call connect_to_server first."
            raise ValueError(msg)

        try:
            result = await self.call_tool(tool_name, arguments)

            # Handle different response formats
            if isinstance(result, dict):
                if "result" in result:
                    return result["result"]
                return result
            if hasattr(result, "content"):
                return {"content": result.content}
            return result  # noqa: TRY300

        except Exception as e:
            logger.error(f"Failed to run tool '{tool_name}': {e}")
            self._connected = False
            raise

    async def close(self):
        """Close the connection and cleanup resources."""
        await self._cleanup_discovery_task()
        await self.exit_stack.aclose()
        self.session = None
        self.connected_transport = None
        self.discovered_endpoint = None
        self._connected = False

    async def _cleanup_discovery_task(self):
        """Clean up the discovery task if running."""
        if self.discovery_task:
            self.discovery_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.discovery_task
            self.discovery_task = None

    def _get_initialize_request_params(self, protocol_version: str) -> dict[str, object]:
        """Get initialization parameters for the MCP session."""
        return {
            "protocolVersion": protocol_version,
            "capabilities": {"tools": {}},
            "clientInfo": {
                "name": "langflow",
                "version": self._version,
            },
        }

    @staticmethod
    def _normalize_tools(tools_raw: list) -> list[StructuredTool]:
        """Convert MCP tools to StructuredTool objects for Langflow compatibility.

        Note: This creates placeholder tool functions that just echo their inputs.
        The actual tool execution happens via the run_tool/call_tool methods, which
        properly route calls to the MCP server. This design supports Langflow's
        tool preview functionality while enabling real server round-trips.
        """
        structured_tools: list[StructuredTool] = []

        for tool in tools_raw:
            try:
                if hasattr(tool, "name") and hasattr(tool, "description"):
                    # MCP Tool object
                    name = tool.name
                    description = tool.description
                    # input_schema = getattr(tool, "inputSchema", {})  # Unused, commenting out
                elif isinstance(tool, dict):
                    # Dictionary representation
                    name = tool.get("name", "")
                    description = tool.get("description", "")
                    # input_schema = tool.get("inputSchema", {})  # Unused, commenting out
                else:
                    logger.warning(f"Skipping unrecognized tool format: {tool}")
                    continue

                if not name:
                    logger.warning(f"Skipping tool with empty name: {tool}")
                    continue

                # Create a simple StructuredTool for Langflow
                # Use closure to capture the current value of name
                def create_tool_func(tool_name):
                    def tool_func(**kwargs):
                        return f"Tool {tool_name} called with {kwargs}"

                    return tool_func

                structured_tool = StructuredTool.from_function(
                    func=create_tool_func(name),
                    name=name,
                    description=description or f"MCP tool: {name}",
                )
                structured_tools.append(structured_tool)

            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Error converting tool to StructuredTool: {e}")
                continue

        return structured_tools

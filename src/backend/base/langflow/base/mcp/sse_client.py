import asyncio
import json
import uuid
from contextlib import suppress
from typing import Any
from urllib.parse import urlparse

import httpx
from httpx import codes as httpx_codes
from langchain_core.tools import StructuredTool
from loguru import logger

# Core SDK re-exports
from mcp import ClientSession, types

from langflow.base.mcp.base_client import BaseMCPClient
from langflow.base.mcp.constants import (
    PROTOCOL_V_2025_03_26,
)

# SSE helper from core SDK
from langflow.utils.version import get_version_info

HTTP_ERROR_STATUS_CODE = httpx_codes.BAD_REQUEST  # HTTP status code for client errors

# Constants for magic numbers
HTTP_STATUS_OK = 200
HTTP_STATUS_NOT_FOUND = 404
HTTP_STATUS_SERVER_ERROR = 500

# Probe buffer limit for discovering first SSE event (bytes/characters)
PROBE_BUFFER_LIMIT = 2048


class MCPConnectionError(Exception):
    """Custom exception for MCP connection errors."""


class MCPTransportError(Exception):
    """Custom exception for MCP transport errors."""


class ProtocolError(ValueError):
    """Raised when the server violates the MCP protocol contract."""


class MCPSseClient(BaseMCPClient[dict[str, Any]]):
    """MCP SSE Client with support for multiple transport protocols.

    Supports:
    - Streamable HTTP transport (MCP 2025-03-26)
    - HTTP+SSE dual-endpoint transport (MCP 2024-11-05)

    Features enhanced retry logic, timeout controls, and transport detection.
    Inherits common functionality from BaseMCPClient while implementing SSE-specific
    connection and tool execution logic.
    """

    def __init__(self) -> None:
        super().__init__()
        self.sse = None

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
                if response.status_code not in (HTTP_STATUS_OK, 202):  # Accept both 200 OK and 202 Accepted
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

                    if event_type and event_data_lines:
                        # Join multi-line data
                        event_data_str = "\n".join(event_data_lines)

                        if event_type == "endpoint" and not endpoint_discovered:
                            # Endpoint events contain plain URI strings, not JSON
                            logger.debug(f"MCP HTTP+SSE endpoint discovered: {event_data_str}")
                            await endpoint_queue.put(("endpoint", {"uri": event_data_str}))
                            endpoint_discovered = True

                        elif event_type == "message":
                            # Message events contain JSON-RPC messages
                            try:
                                event_data = json.loads(event_data_str)
                                logger.debug(f"MCP HTTP+SSE message received: {event_data}")

                                # Check if this is a response to a pending request
                                if isinstance(event_data, dict) and "id" in event_data:
                                    request_id = str(event_data["id"])
                                    logger.debug(f"HTTP+SSE response received for request ID: {request_id}")
                                    if request_id in self.response_futures:
                                        future = self.response_futures.pop(request_id)
                                        if not future.done():
                                            logger.debug(f"Setting result for request ID: {request_id}")
                                            future.set_result(event_data)
                                    else:
                                        logger.debug(f"No pending future found for request ID: {request_id}")

                                # Also put it in the queue for the transport handler
                                await endpoint_queue.put(("message", event_data))
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse SSE message as JSON: {e}")
                                await endpoint_queue.put(("error", f"Invalid JSON in SSE message: {event_data_str}"))
                                return

        except (httpx.HTTPError, asyncio.TimeoutError, Exception) as e:
            logger.debug(f"HTTP+SSE discovery handler error: {e}")
            await endpoint_queue.put(("error", f"HTTP+SSE discovery error: {e}"))

    async def _mcp_http_sse_send_request(self, request_data: dict) -> dict:
        """Send a JSON-RPC request via HTTP+SSE and wait for response."""
        if not self.discovered_endpoint:
            msg = "No HTTP+SSE endpoint discovered"
            raise RuntimeError(msg)

        # Generate request ID if not present
        if "id" not in request_data:
            request_data["id"] = str(uuid.uuid4())

        request_id = str(request_data["id"])

        # Create a future for the response
        response_future: asyncio.Future[dict] = asyncio.Future()
        self.response_futures[request_id] = response_future

        try:
            # Send the request via HTTP POST
            await self._send_http_sse_request(request_data)

            # Wait for response via SSE stream (handled by discovery task)
            response = await asyncio.wait_for(response_future, timeout=30.0)
        except asyncio.TimeoutError as exc:
            # Clean up the future and re-raise with clearer context
            self.response_futures.pop(request_id, None)
            msg = "HTTP+SSE request timed out"
            raise asyncio.TimeoutError(msg) from exc
        except Exception:
            # Clean up the future and propagate the original error
            self.response_futures.pop(request_id, None)
            raise
        else:
            return response

    async def _try_http_sse_transport(
        self,
        url: str,
        headers: dict[str, str] | None,
        _timeout_seconds: int,  # Unused but kept for API compatibility
    ) -> bool:
        """Try HTTP+SSE transport (MCP 2024-11-05)."""
        logger.debug(f"Attempting HTTP+SSE transport (MCP 2024-11-05) at {url}")

        try:
            # Create a queue for endpoint discovery and message handling
            endpoint_queue: asyncio.Queue[tuple[str, str | dict]] = asyncio.Queue()

            # Start the discovery handler task
            discovery_task = asyncio.create_task(self._mcp_http_sse_discovery_handler(url, headers, endpoint_queue))

            # Wait for endpoint discovery
            while True:
                try:
                    event_type, event_data = await asyncio.wait_for(endpoint_queue.get(), timeout=10.0)

                    if event_type == "endpoint" and isinstance(event_data, dict) and "uri" in event_data:
                        from urllib.parse import urljoin

                        endpoint_uri: str = event_data["uri"]
                        if not endpoint_uri.lower().startswith("http"):
                            endpoint_uri = urljoin(url, endpoint_uri)

                        self.discovered_endpoint = endpoint_uri
                        logger.debug(f"HTTP+SSE endpoint discovered: {self.discovered_endpoint}")

                        # Now that we have the endpoint, try to initialize
                        # Keep the SSE connection open and use it for responses
                        try:
                            init_request = {
                                "jsonrpc": "2.0",
                                "id": "init-1",  # Add ID for response matching
                                "method": "initialize",
                                "params": self._get_initialize_request_params("2024-11-05"),
                            }

                            # Send the initialization request
                            await self._mcp_http_sse_send_request(init_request)

                            # Wait for the initialization response via SSE
                            while True:
                                try:
                                    response_type, response_data = await asyncio.wait_for(
                                        endpoint_queue.get(), timeout=30.0
                                    )

                                    if response_type == "message" and isinstance(response_data, dict):
                                        if response_data.get("id") == "init-1" and "result" in response_data:
                                            self.init_result = types.InitializeResult(**response_data["result"])
                                            logger.info("HTTP+SSE session initialized successfully")

                                            # Store the discovery task for cleanup later
                                            self.discovery_task = discovery_task
                                            return True
                                        if response_data.get("id") == "init-1" and "error" in response_data:
                                            logger.debug(f"HTTP+SSE initialization error: {response_data['error']}")
                                            break
                                    elif response_type == "error":
                                        logger.debug(f"HTTP+SSE initialization failed: {response_data}")
                                        break

                                except asyncio.TimeoutError:
                                    logger.debug("HTTP+SSE initialization timed out")
                                    break

                        except (ConnectionError, OSError, httpx.HTTPError, asyncio.TimeoutError, ValueError) as exc:
                            # Transport initialization failed - expected during transport probing
                            logger.debug(f"HTTP+SSE initialization failed: {exc}")
                            break

                    elif event_type == "error":
                        logger.debug(f"HTTP+SSE endpoint discovery failed: {event_data}")
                        break

                except asyncio.TimeoutError:
                    logger.debug("HTTP+SSE endpoint discovery timed out")
                    break

        except (ConnectionError, OSError, httpx.HTTPError, asyncio.TimeoutError, ValueError) as exc:
            # Transport setup failed - expected during multi-transport connection attempts
            logger.debug(f"HTTP+SSE transport setup failed: {exc}")

        # Clean up discovery task if initialization failed
        if "discovery_task" in locals():
            discovery_task.cancel()
            with suppress(asyncio.CancelledError):
                await discovery_task

        return False

    async def connect_to_server_with_retry(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout_seconds: int | None = None,
        sse_read_timeout_seconds: int = 30,
        max_retries: int | None = None,
        *,
        connect_timeout_seconds: int | None = 10,
    ):
        """Connect to server with retry logic and exponential backoff.

        New in v0.5:
            connect_timeout_seconds -- per-attempt connection timeout that is
            enforced for the underlying ``connect_to_server`` call.  Keeping
            this relatively small ensures that retries happen quickly when the
            remote endpoint is still booting or temporarily unavailable.
        """
        # Resolve effective per-attempt timeout - explicit ``timeout_seconds`` still wins
        # for backwards-compatibility, otherwise fall back to the new
        # ``connect_timeout_seconds`` shortcut.  Ensure that the value is an ``int``
        if timeout_seconds is None:
            timeout_seconds = connect_timeout_seconds

        # Guarantee that ``timeout_seconds`` is an ``int`` to satisfy type checkers
        if not isinstance(timeout_seconds, int):
            msg = "timeout_seconds must be an int"
            raise TypeError(msg)

        max_retries = max_retries or self.max_retries
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                return await self.connect_to_server(
                    url,
                    headers,
                    timeout_seconds,
                    sse_read_timeout_seconds,
                )
            except (ConnectionError, OSError, httpx.HTTPError, asyncio.TimeoutError, MCPTransportError) as e:
                last_exception = e
                if attempt < max_retries:
                    target_delay = self._calculate_retry_delay(attempt)
                    logger.debug(
                        "Connection attempt %d failed, sleeping %.2fs before next: %s",
                        attempt + 1,
                        target_delay,
                        e,
                    )
                    await asyncio.sleep(target_delay)
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
    ) -> list[types.Tool]:
        """Connect to MCP server with transport detection and fallback."""
        is_valid, error_msg = await self.validate_url(url)
        if not is_valid:
            msg = f"Invalid URL: {error_msg}"
            raise ValueError(msg)

        # Optionally follow a single redirect to respect standard web behaviour
        url = await self.pre_check_redirect(url) or url

        # Store connection parameters
        self._connection_params = {
            "url": url,
            "headers": headers,
            "timeout_seconds": timeout_seconds,
        }

        # ------------------------------------------------------------------
        # Quick optimisation:
        # If the URL already serves ``text/event-stream`` (i.e. the legacy
        # HTTP+SSE discovery stream) there is no point in first trying the
        # newer Streamable-HTTP transport.  We therefore probe the headers and
        # *start* with HTTP+SSE when it looks appropriate.
        # ------------------------------------------------------------------

        try_http_sse_first = await self._looks_like_http_sse(url, headers)

        logger.debug("connect_to_server: initial probe indicates HTTP+SSE=%s", try_http_sse_first)

        if not try_http_sse_first:
            # Phase 1: Try Streamable HTTP (MCP 2025-03-26)
            logger.debug("Phase 1: Streamable-HTTP probe")
            streamable_session_cm = await self._try_streamable_http_transport(url, headers, timeout_seconds)
        else:
            logger.debug("Phase 1 skipped: endpoint already looks like HTTP+SSE")
            streamable_session_cm = None

        if streamable_session_cm is not None:
            try:
                self.session = await self.exit_stack.enter_async_context(streamable_session_cm)
            except (ConnectionError, httpx.HTTPError, asyncio.TimeoutError, Exception) as exc:
                # Streamable HTTP looked promising (context manager returned) but the
                # actual handshake failed.  Log and continue with HTTP+SSE
                logger.debug(
                    "Streamable HTTP context enter failed - falling back to HTTP+SSE: %s",
                    exc,
                )
                self.session = None
                streamable_session_cm = None  # signal failure so we try fallback below
            else:
                self.connected_transport = "streamable_http"
                self._connected = True

                # Capture protocol information for Streamable HTTP transport
                self._capture_streamable_http_protocol_info()

                # Get tools from session
                if self.session is None:
                    msg = "Session is None after successful initialization"
                    raise RuntimeError(msg)
                response = await self.session.list_tools()
                logger.info(
                    "Successfully connected via Streamable HTTP, found %d tools",
                    len(response.tools),
                )
                return response.tools

        # Phase 2: Try HTTP+SSE (MCP 2024-11-05)
        logger.debug("Phase 2: Attempting HTTP+SSE transport")
        http_sse_success = await self._try_http_sse_transport(url, headers, timeout_seconds)

        logger.debug(f"connect_to_server: HTTP+SSE result http_sse_success={http_sse_success}")

        if http_sse_success:
            self.connected_transport = "http_sse"
            self._connected = True

            # Capture protocol information for HTTP+SSE transport
            self._capture_http_sse_protocol_info()

            # Get tools via HTTP+SSE
            tools_request = {"jsonrpc": "2.0", "id": "tools-1", "method": "tools/list"}
            tools_response = await self._mcp_http_sse_send_request(tools_request)

            if "result" in tools_response and "tools" in tools_response["result"]:
                raw_tools = tools_response["result"]["tools"]
                tools_list = [types.Tool(**tool) for tool in raw_tools]
                logger.info(f"Successfully connected via HTTP+SSE, found {len(tools_list)} tools")
                return tools_list

        # Phase 3: Both transports failed
        error_msg = (
            f"Both transport methods failed for {url}. Tried: Streamable HTTP (2025-03-26), HTTP+SSE (2024-11-05)\n\n"
            "Troubleshooting tips:\n"
            "- Verify the server URL is correct and reachable.\n"
            "- Ensure the server supports at least one of the above transport protocols.\n"
            "- Check that the server process is running and not blocked by a firewall."
        )
        logger.error(error_msg)
        raise MCPTransportError(error_msg)

    def _capture_streamable_http_protocol_info(self) -> None:
        """Capture protocol information for successful Streamable HTTP connection."""
        from datetime import datetime, timezone

        if not self.session or not hasattr(self.session, "init_result"):
            # Fallback if init_result is not available
            self.protocol_info = {
                "protocol_version": PROTOCOL_V_2025_03_26,  # default to latest known
                "transport_type": "streamable_http",
                "capabilities": {},
                "server_info": {},
                "last_detected": datetime.now(timezone.utc).isoformat(),
            }
            return

        init_result = self.session.init_result
        self.protocol_info = {
            "protocol_version": getattr(init_result, "protocolVersion", PROTOCOL_V_2025_03_26),
            "transport_type": "streamable_http",
            "capabilities": getattr(init_result, "capabilities", {}),
            "server_info": getattr(init_result, "serverInfo", {}),
            "last_detected": datetime.now(timezone.utc).isoformat(),
        }
        logger.debug("Captured Streamable HTTP protocol info: %s", self.protocol_info)

    def _capture_http_sse_protocol_info(self) -> None:
        """Capture protocol information for an HTTP+SSE handshake.

        The MCP specification requires that the *init* event payload **MUST**
        include a ``protocolVersion`` field.  Missing or unknown versions are
        surfaced as :class:`ProtocolError` instead of being silently
        defaulted.
        """
        from datetime import datetime, timezone

        if not self.init_result or not getattr(self.init_result, "protocolVersion", None):
            msg = "Missing protocolVersion in server init event"
            raise ProtocolError(msg)

        self.protocol_info = {
            "protocol_version": self.init_result.protocolVersion,
            "transport_type": "http_sse",
            "capabilities": getattr(self.init_result, "capabilities", {}),
            "server_info": getattr(self.init_result, "serverInfo", {}),
            "last_detected": datetime.now(timezone.utc).isoformat(),
        }
        logger.debug("Captured HTTP+SSE protocol info: %s", self.protocol_info)

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

                return tool_objects

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

            return raw_tools

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

    async def _execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Execute *tool_name* with *arguments* and return the raw JSON-RPC envelope.

        According to the JSON-RPC 2.0 spec the result **must** be wrapped in an
        object that may contain either a ``result`` *or* an ``error`` key. This
        behaviour always returns the full envelope so downstream code can handle
        success and error cases uniformly.
        """
        try:
            result = await self.call_tool(tool_name, arguments)

            # Normalise *result* into a predictable structure:
            #   • If JSON-RPC dict -> return as-is
            #   • If LangChain content wrapper -> coerce into dict for
            #     transport-agnostic handling
            if isinstance(result, dict):
                return result

            if hasattr(result, "content"):
                return {"content": result.content}

            # Fallback to whatever the transport returned (str, dataclass, …)
            return result  # noqa: TRY300

        except Exception as e:
            logger.error(f"Failed to run tool '{tool_name}': {e}")
            self._connected = False
            raise

    async def _cleanup_transport(self):
        """Perform SSE-specific cleanup operations."""
        await self._cleanup_discovery_task()
        self.connected_transport = None
        self.discovered_endpoint = None

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

    async def pre_check_redirect(self, url: str | None) -> str | None:
        """Follow a single HTTP redirect (3xx) and return the final URL.

        This does not constitute speculative endpoint discovery -
        we only respect an explicit redirect response from the server.

        Args:
            url: Original URL provided by the caller.

        Returns:
            The final URL after applying a single redirect, or the original
            URL if no redirect occurs / on any error.
        """
        if url is None:
            return url

        try:
            async with httpx.AsyncClient(follow_redirects=False, timeout=5.0) as client:
                response = await client.head(url)

            if response.status_code in {
                httpx.codes.MOVED_PERMANENTLY,  # 301
                httpx.codes.FOUND,  # 302
                httpx.codes.SEE_OTHER,  # 303
                httpx.codes.TEMPORARY_REDIRECT,  # 307
                httpx.codes.PERMANENT_REDIRECT,  # 308
            }:
                return response.headers.get("Location", url)

        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.debug(f"Redirect check failed for {url}: {exc}")

        return url

    # ---------------------------------------------------------------------
    # Transport detection helpers
    # ---------------------------------------------------------------------

    async def _looks_like_http_sse(self, url: str, headers: dict[str, str] | None) -> bool:
        """Quick probe to see if *url* is an MCP **HTTP + SSE** discovery stream.

        Spec-driven approach (MCP 2024-11-05):

        1. Send a `GET` request with ``Accept: text/event-stream``.
        2. Verify the HTTP response is ``200`` and ``Content-Type`` contains
           ``text/event-stream``.
        3. Read *at most* the first event chunk (bounded to avoid hanging).
        4. If the first event is ``event: init`` we can confidently assume the
           endpoint is an MCP discovery stream.

        Any network failure, timeout, or mismatching event leads to ``False`` so
        the caller can safely fall back to Streamable-HTTP probing.
        """
        request_headers = {"Accept": "text/event-stream", **(headers or {})}
        logger.debug("_looks_like_http_sse: probing %s for init event", url)

        try:
            async with (
                httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client,
                client.stream("GET", url, headers=request_headers) as resp,
            ):
                if resp.status_code != HTTP_STATUS_OK:
                    logger.debug("_looks_like_http_sse: non-200 status %s", resp.status_code)
                    return False

                if "text/event-stream" not in resp.headers.get("content-type", "").lower():
                    logger.debug(
                        "_looks_like_http_sse: content-type %s not SSE",
                        resp.headers.get("content-type"),
                    )
                    return False

                # Read just enough bytes to capture the first SSE event
                buffer = ""
                async for chunk in resp.aiter_text():
                    buffer += chunk
                    if "\n\n" in buffer or len(buffer) > PROBE_BUFFER_LIMIT:
                        break

                event_type = None
                data_lines = []
                for line in buffer.splitlines():
                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[5:].strip())

                if event_type == "init":
                    logger.debug("_looks_like_http_sse: init event detected - SSE confirmed")
                    return True

        except (httpx.HTTPError, asyncio.TimeoutError, OSError, ConnectionError, ValueError) as exc:
            logger.debug("_looks_like_http_sse: probe error - %s", exc)
            return False

        logger.debug("_looks_like_http_sse: init event not found - returning False")
        return False

    async def _send_http_sse_request(self, request_data: dict) -> None:
        """Send a request to the HTTP+SSE messages endpoint."""
        if not self.discovered_endpoint:
            msg = "No HTTP+SSE endpoint discovered"
            raise RuntimeError(msg)

        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.discovered_endpoint,
                json=request_data,
                headers=request_headers,
            )

            if response.status_code not in (HTTP_STATUS_OK, 202):  # Accept both 200 OK and 202 Accepted
                error_msg = f"HTTP+SSE request failed with status {response.status_code}"
                raise httpx.HTTPStatusError(error_msg, request=response.request, response=response)

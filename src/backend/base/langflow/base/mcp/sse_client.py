import asyncio
import json
from contextlib import suppress
from typing import Any
from urllib.parse import urlparse, urljoin
import uuid

import httpx
from httpx import codes as httpx_codes
from langchain_core.tools import StructuredTool
from loguru import logger

# Core SDK re-exports
from mcp import ClientSession, types

from langflow.base.mcp.base_client import BaseMCPClient

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
            msg = "No HTTP+SSE endpoint available"
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
            return response

        except asyncio.TimeoutError:
            # Clean up the future
            self.response_futures.pop(request_id, None)
            msg = "HTTP+SSE request timed out"
            raise asyncio.TimeoutError(msg)
        except Exception as e:
            # Clean up the future
            self.response_futures.pop(request_id, None)
            raise e

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
            discovery_task = asyncio.create_task(
                self._mcp_http_sse_discovery_handler(url, headers, endpoint_queue)
            )

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
                                    response_type, response_data = await asyncio.wait_for(endpoint_queue.get(), timeout=30.0)
                                    
                                    if response_type == "message" and isinstance(response_data, dict):
                                        if response_data.get("id") == "init-1" and "result" in response_data:
                                            self.init_result = types.InitializeResult(**response_data["result"])
                                            logger.info("HTTP+SSE session initialized successfully")
                                            
                                            # Store the discovery task for cleanup later
                                            self.discovery_task = discovery_task
                                            return True
                                        elif response_data.get("id") == "init-1" and "error" in response_data:
                                            logger.debug(f"HTTP+SSE initialization error: {response_data['error']}")
                                            break
                                    elif response_type == "error":
                                        logger.debug(f"HTTP+SSE initialization failed: {response_data}")
                                        break
                                        
                                except asyncio.TimeoutError:
                                    logger.debug("HTTP+SSE initialization timed out")
                                    break
                                    
                        except Exception as e:
                            logger.debug(f"HTTP+SSE initialization failed: {e}")
                            break

                    elif event_type == "error":
                        logger.debug(f"HTTP+SSE endpoint discovery failed: {event_data}")
                        break

                except asyncio.TimeoutError:
                    logger.debug("HTTP+SSE endpoint discovery timed out")
                    break

        except Exception as e:
            logger.debug(f"HTTP+SSE transport setup failed: {e}")

        # Clean up discovery task if initialization failed
        if 'discovery_task' in locals():
            discovery_task.cancel()
            try:
                await discovery_task
            except asyncio.CancelledError:
                pass

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
        # Resolve effective per-attempt timeout – explicit ``timeout_seconds``
        # still wins for backwards-compatibility, otherwise fall back to the new
        # ``connect_timeout_seconds`` shortcut.
        if timeout_seconds is None:
            timeout_seconds = connect_timeout_seconds

        max_retries = max_retries or self.max_retries
        last_exception = None

        for attempt in range(max_retries + 1):
            attempt_started = asyncio.get_running_loop().time()
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
        # Heuristic: if the endpoint already advertises *text/event-stream*
        # (legacy HTTP+SSE discovery stream), skip the Streamable-HTTP probe
        # and proceed directly to HTTP+SSE.
        # ------------------------------------------------------------------

        try_http_sse_first = await self._looks_like_http_sse(url, headers)
        
        logger.debug(f"connect_to_server: heuristic result try_http_sse_first={try_http_sse_first}")

        if not try_http_sse_first:
            # Phase 1: Try Streamable HTTP (MCP 2025-03-26)
            logger.debug("Phase 1: Attempting Streamable HTTP transport")
            streamable_session_cm = await self._try_streamable_http_transport(url, headers, timeout_seconds)
        else:
            logger.debug("Phase 1: Skipping Streamable HTTP due to heuristic")
            streamable_session_cm = None

        if streamable_session_cm is not None:
            try:
                self.session = await self.exit_stack.enter_async_context(streamable_session_cm)
            except (ConnectionError, httpx.HTTPError, asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001
                # Streamable HTTP looked promising (context manager returned) but the
                # actual handshake failed.  Log and continue with HTTP+SSE
                logger.debug(
                    "Streamable HTTP context enter failed – falling back to HTTP+SSE: %s",
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
            f"Both transport methods failed for {url}. Tried: Streamable HTTP (2025-03-26), HTTP+SSE (2024-11-05)"
        )
        logger.error(error_msg)
        raise MCPTransportError(error_msg)

    def _capture_streamable_http_protocol_info(self) -> None:
        """Capture protocol information for successful Streamable HTTP connection."""
        from datetime import datetime, timezone

        if not self.session or not hasattr(self.session, "init_result"):
            # Fallback if init_result is not available
            self.protocol_info = {
                "protocol_version": "2025-03-26",  # Streamable HTTP is 2025-03-26
                "transport_type": "streamable_http",
                "capabilities": {},
                "server_info": {},
                "last_detected": datetime.now(timezone.utc).isoformat()
            }
            return

        init_result = self.session.init_result
        self.protocol_info = {
            "protocol_version": getattr(init_result, "protocolVersion", "2025-03-26"),
            "transport_type": "streamable_http",
            "capabilities": getattr(init_result, "capabilities", {}),
            "server_info": getattr(init_result, "serverInfo", {}),
            "last_detected": datetime.now(timezone.utc).isoformat()
        }
        logger.debug(f"Captured Streamable HTTP protocol info: {self.protocol_info}")

    def _capture_http_sse_protocol_info(self) -> None:
        """Capture protocol information for successful HTTP+SSE connection."""
        from datetime import datetime, timezone

        if not self.init_result:
            # Fallback if init_result is not available
            self.protocol_info = {
                "protocol_version": "2024-11-05",  # HTTP+SSE is 2024-11-05
                "transport_type": "http_sse",
                "capabilities": {},
                "server_info": {},
                "last_detected": datetime.now(timezone.utc).isoformat()
            }
            return

        self.protocol_info = {
            "protocol_version": getattr(self.init_result, "protocolVersion", "2024-11-05"),
            "transport_type": "http_sse",
            "capabilities": getattr(self.init_result, "capabilities", {}),
            "server_info": getattr(self.init_result, "serverInfo", {}),
            "last_detected": datetime.now(timezone.utc).isoformat()
        }
        logger.debug(f"Captured HTTP+SSE protocol info: {self.protocol_info}")

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
        """Execute a tool using SSE transport (reuses existing session).

        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments for the tool

        Returns:
            Result of the tool execution

        Raises:
            ValueError: For invalid tool parameters or execution failures
        """
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

        This does not constitute speculative endpoint discovery –
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
                httpx.codes.FOUND,              # 302
                httpx.codes.SEE_OTHER,          # 303
                httpx.codes.TEMPORARY_REDIRECT, # 307
                httpx.codes.PERMANENT_REDIRECT, # 308
            }:
                return response.headers.get("Location", url)

        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.debug(f"Redirect check failed for {url}: {exc}")

        return url

    # ---------------------------------------------------------------------
    # Transport detection helpers
    # ---------------------------------------------------------------------

    async def _looks_like_http_sse(self, url: str, headers: dict[str, str] | None) -> bool:  # noqa: C901 (complexity ok)
        """Return *True* if *url* appears to be an HTTP+SSE discovery stream.

        Heuristics (all driven by spec 2024-11-05):

        1.  HEAD returns *Content-Type: text/event-stream*
        2.  If HEAD is not allowed (405) or the server sends 5xx, issue a GET
            and examine the first response headers.

        Any failure (timeout, network error, unexpected status) is treated as
        *False* so we safely fall back to the normal Streamable-HTTP probe.
        """

        request_headers = {"Accept": "text/event-stream", **(headers or {})}
        logger.debug(f"_looks_like_http_sse: probing {url} with headers {request_headers}")

        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                # Prefer HEAD when available – cheaper and side-effect free
                try:
                    head_resp = await client.head(url, headers=request_headers)
                    logger.debug(f"_looks_like_http_sse: HEAD {url} -> {head_resp.status_code}, content-type: {head_resp.headers.get('content-type', 'NONE')}")
                    if "text/event-stream" in head_resp.headers.get("content-type", "").lower():
                        logger.debug(f"_looks_like_http_sse: HEAD indicates SSE, returning True")
                        return True
                    # Regardless of status code, continue with GET probe – some
                    # servers either don't implement HEAD correctly or return
                    # misleading headers.
                except httpx.HTTPError as e:
                    logger.debug(f"_looks_like_http_sse: HEAD failed with {e}, falling through to GET")
                    # Errors are not fatal for the heuristic – fall through to GET
                    pass

                # Fallback: open a GET stream but read no body (headers only)
                try:
                    async with client.stream("GET", url, headers=request_headers) as resp_stream:
                        logger.debug(f"_looks_like_http_sse: GET {url} -> {resp_stream.status_code}, content-type: {resp_stream.headers.get('content-type', 'NONE')}")
                        if "text/event-stream" in resp_stream.headers.get("content-type", "").lower():
                            logger.debug(f"_looks_like_http_sse: GET indicates SSE, returning True")
                            return True
                except httpx.HTTPError as e:
                    logger.debug(f"_looks_like_http_sse: GET failed with {e}")
                    pass
        except Exception as e:
            logger.debug(f"_looks_like_http_sse: outer exception {e}")
            # Generic guard – any unknown failure means "not SSE"
            return False

        logger.debug(f"_looks_like_http_sse: no SSE detected, returning False")
        return False

    async def _send_http_sse_request(self, request_data: dict) -> None:
        """Send a request to the HTTP+SSE messages endpoint."""
        if not self.discovered_endpoint:
            raise RuntimeError("No HTTP+SSE endpoint discovered")

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

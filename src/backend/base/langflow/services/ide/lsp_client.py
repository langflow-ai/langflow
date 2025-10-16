"""
LSP Client for Genesis Language Server - Phase 4 IDE Integration.

Provides client-side LSP functionality for connecting to the Genesis Language Server
with enhanced error handling, connection management, and developer experience features.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

import websockets

logger = logging.getLogger(__name__)


class LSPMessageType(Enum):
    """LSP message types."""
    REQUEST = 1
    RESPONSE = 2
    NOTIFICATION = 3
    ERROR = 4


@dataclass
class LSPMessage:
    """LSP message structure."""
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    message_type: LSPMessageType = LSPMessageType.REQUEST


class GenesisLSPClient:
    """
    LSP Client for Genesis Language Server with Phase 4 enhancements.

    Provides comprehensive client-side LSP functionality including:
    - Connection management and reconnection
    - Request/response handling
    - Real-time notifications
    - Error handling and recovery
    - Performance monitoring
    """

    def __init__(self, host: str = "localhost", port: int = 8080):
        """
        Initialize Genesis LSP client.

        Args:
            host: Language server host
            port: Language server port
        """
        self.host = host
        self.port = port
        self.websocket = None
        self.connected = False
        self.request_id = 0
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.notification_handlers: Dict[str, List[Callable]] = {}
        self.connection_callbacks: List[Callable] = []
        self.performance_metrics = {
            "requests_sent": 0,
            "responses_received": 0,
            "notifications_received": 0,
            "errors_encountered": 0,
            "average_response_time": 0.0
        }

    async def connect(self) -> bool:
        """
        Connect to Genesis Language Server.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            uri = f"ws://{self.host}:{self.port}"
            logger.info(f"Connecting to Genesis Language Server at {uri}")

            self.websocket = await websockets.connect(uri)
            self.connected = True

            # Start message handling task
            asyncio.create_task(self._handle_messages())

            # Send initialize request
            await self._send_initialize_request()

            # Notify connection callbacks
            for callback in self.connection_callbacks:
                await callback(True)

            logger.info("Successfully connected to Genesis Language Server")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Genesis Language Server: {e}")
            self.connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from Genesis Language Server."""
        try:
            if self.websocket and self.connected:
                # Send shutdown notification
                await self._send_notification("shutdown")

                await self.websocket.close()
                self.connected = False

                # Notify connection callbacks
                for callback in self.connection_callbacks:
                    await callback(False)

                logger.info("Disconnected from Genesis Language Server")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")

    async def send_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0
    ) -> Any:
        """
        Send LSP request and wait for response.

        Args:
            method: LSP method name
            params: Request parameters
            timeout: Request timeout in seconds

        Returns:
            Response result

        Raises:
            ConnectionError: If not connected to server
            TimeoutError: If request times out
            RuntimeError: If server returns error
        """
        if not self.connected:
            raise ConnectionError("Not connected to Language Server")

        request_id = str(self.request_id)
        self.request_id += 1

        message = LSPMessage(
            method=method,
            params=params,
            id=request_id,
            message_type=LSPMessageType.REQUEST
        )

        # Create future for response
        future = asyncio.Future()
        self.pending_requests[request_id] = future

        try:
            # Send request
            await self._send_message(message)
            self.performance_metrics["requests_sent"] += 1

            # Wait for response
            result = await asyncio.wait_for(future, timeout=timeout)
            self.performance_metrics["responses_received"] += 1

            return result

        except asyncio.TimeoutError:
            # Clean up pending request
            if request_id in self.pending_requests:
                del self.pending_requests[request_id]
            self.performance_metrics["errors_encountered"] += 1
            raise TimeoutError(f"Request {method} timed out after {timeout}s")

        except Exception as e:
            # Clean up pending request
            if request_id in self.pending_requests:
                del self.pending_requests[request_id]
            self.performance_metrics["errors_encountered"] += 1
            raise RuntimeError(f"Request {method} failed: {e}")

    async def send_notification(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        """
        Send LSP notification (no response expected).

        Args:
            method: LSP method name
            params: Notification parameters
        """
        if not self.connected:
            raise ConnectionError("Not connected to Language Server")

        message = LSPMessage(
            method=method,
            params=params,
            message_type=LSPMessageType.NOTIFICATION
        )

        await self._send_message(message)

    def add_notification_handler(self, method: str, handler: Callable) -> None:
        """
        Add handler for specific notification type.

        Args:
            method: Notification method to handle
            handler: Async function to handle notification
        """
        if method not in self.notification_handlers:
            self.notification_handlers[method] = []

        self.notification_handlers[method].append(handler)

    def add_connection_callback(self, callback: Callable) -> None:
        """
        Add callback for connection state changes.

        Args:
            callback: Async function called with connection state (bool)
        """
        self.connection_callbacks.append(callback)

    # Document lifecycle methods

    async def did_open_document(self, uri: str, language_id: str, version: int, text: str) -> None:
        """
        Notify server that document was opened.

        Args:
            uri: Document URI
            language_id: Language identifier (e.g., "genesis-yaml")
            version: Document version
            text: Document content
        """
        params = {
            "textDocument": {
                "uri": uri,
                "languageId": language_id,
                "version": version,
                "text": text
            }
        }

        await self.send_notification("textDocument/didOpen", params)

    async def did_change_document(
        self,
        uri: str,
        version: int,
        changes: List[Dict[str, Any]]
    ) -> None:
        """
        Notify server of document changes.

        Args:
            uri: Document URI
            version: New document version
            changes: List of text changes
        """
        params = {
            "textDocument": {
                "uri": uri,
                "version": version
            },
            "contentChanges": changes
        }

        await self.send_notification("textDocument/didChange", params)

    async def did_save_document(self, uri: str, text: Optional[str] = None) -> None:
        """
        Notify server that document was saved.

        Args:
            uri: Document URI
            text: Optional document content
        """
        params = {
            "textDocument": {
                "uri": uri
            }
        }

        if text is not None:
            params["text"] = text

        await self.send_notification("textDocument/didSave", params)

    async def did_close_document(self, uri: str) -> None:
        """
        Notify server that document was closed.

        Args:
            uri: Document URI
        """
        params = {
            "textDocument": {
                "uri": uri
            }
        }

        await self.send_notification("textDocument/didClose", params)

    # Language feature methods

    async def get_completion(
        self,
        uri: str,
        line: int,
        character: int,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Request completion suggestions.

        Args:
            uri: Document URI
            line: Line number (0-based)
            character: Character position (0-based)
            context: Completion context

        Returns:
            List of completion items
        """
        params = {
            "textDocument": {
                "uri": uri
            },
            "position": {
                "line": line,
                "character": character
            }
        }

        if context:
            params["context"] = context

        result = await self.send_request("textDocument/completion", params)
        return result.get("items", []) if result else []

    async def get_hover(self, uri: str, line: int, character: int) -> Optional[Dict[str, Any]]:
        """
        Request hover information.

        Args:
            uri: Document URI
            line: Line number (0-based)
            character: Character position (0-based)

        Returns:
            Hover information or None
        """
        params = {
            "textDocument": {
                "uri": uri
            },
            "position": {
                "line": line,
                "character": character
            }
        }

        return await self.send_request("textDocument/hover", params)

    async def get_diagnostics(self, uri: str) -> List[Dict[str, Any]]:
        """
        Request document diagnostics.

        Args:
            uri: Document URI

        Returns:
            List of diagnostic items
        """
        params = {
            "textDocument": {
                "uri": uri
            }
        }

        result = await self.send_request("textDocument/diagnostic", params)
        return result.get("items", []) if result else []

    async def get_code_actions(
        self,
        uri: str,
        start_line: int,
        start_character: int,
        end_line: int,
        end_character: int,
        diagnostics: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Request code actions for range.

        Args:
            uri: Document URI
            start_line: Start line (0-based)
            start_character: Start character (0-based)
            end_line: End line (0-based)
            end_character: End character (0-based)
            diagnostics: Related diagnostics

        Returns:
            List of code actions
        """
        params = {
            "textDocument": {
                "uri": uri
            },
            "range": {
                "start": {
                    "line": start_line,
                    "character": start_character
                },
                "end": {
                    "line": end_line,
                    "character": end_character
                }
            },
            "context": {
                "diagnostics": diagnostics or []
            }
        }

        result = await self.send_request("textDocument/codeAction", params)
        return result if result else []

    # Performance and monitoring methods

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get client performance metrics.

        Returns:
            Dictionary of performance metrics
        """
        return self.performance_metrics.copy()

    def reset_performance_metrics(self) -> None:
        """Reset performance metrics."""
        self.performance_metrics = {
            "requests_sent": 0,
            "responses_received": 0,
            "notifications_received": 0,
            "errors_encountered": 0,
            "average_response_time": 0.0
        }

    # Private methods

    async def _send_initialize_request(self) -> None:
        """Send LSP initialize request."""
        params = {
            "processId": None,
            "clientInfo": {
                "name": "Genesis LSP Client",
                "version": "1.0.0"
            },
            "capabilities": {
                "textDocument": {
                    "synchronization": {
                        "dynamicRegistration": True,
                        "willSave": True,
                        "willSaveWaitUntil": True,
                        "didSave": True
                    },
                    "completion": {
                        "dynamicRegistration": True,
                        "completionItem": {
                            "snippetSupport": True,
                            "commitCharactersSupport": True,
                            "documentationFormat": ["markdown", "plaintext"]
                        }
                    },
                    "hover": {
                        "dynamicRegistration": True,
                        "contentFormat": ["markdown", "plaintext"]
                    },
                    "codeAction": {
                        "dynamicRegistration": True,
                        "codeActionLiteralSupport": {
                            "codeActionKind": {
                                "valueSet": [
                                    "quickfix",
                                    "refactor",
                                    "source"
                                ]
                            }
                        }
                    },
                    "diagnostic": {
                        "dynamicRegistration": True
                    }
                }
            },
            "workspaceFolders": None
        }

        await self.send_request("initialize", params)

        # Send initialized notification
        await self.send_notification("initialized")

    async def _send_message(self, message: LSPMessage) -> None:
        """Send LSP message to server."""
        if not self.websocket:
            raise ConnectionError("WebSocket connection not available")

        # Convert to LSP JSON-RPC format
        data = {
            "jsonrpc": "2.0",
            "method": message.method
        }

        if message.id is not None:
            data["id"] = message.id

        if message.params is not None:
            data["params"] = message.params

        if message.result is not None:
            data["result"] = message.result

        if message.error is not None:
            data["error"] = message.error

        # Send as JSON
        json_data = json.dumps(data)
        await self.websocket.send(json_data)

        logger.debug(f"Sent LSP message: {message.method}")

    async def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Send LSP notification."""
        message = LSPMessage(
            method=method,
            params=params,
            message_type=LSPMessageType.NOTIFICATION
        )

        await self._send_message(message)

    async def _handle_messages(self) -> None:
        """Handle incoming messages from server."""
        try:
            async for message in self.websocket:
                await self._process_message(message)

        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
            self.connected = False
        except Exception as e:
            logger.error(f"Error handling messages: {e}")
            self.connected = False

    async def _process_message(self, raw_message: str) -> None:
        """Process incoming LSP message."""
        try:
            data = json.loads(raw_message)

            # Handle response
            if "id" in data and data["id"] in self.pending_requests:
                future = self.pending_requests.pop(data["id"])

                if "error" in data:
                    error = data["error"]
                    future.set_exception(RuntimeError(f"LSP Error: {error.get('message', 'Unknown error')}"))
                else:
                    future.set_result(data.get("result"))

            # Handle notification
            elif "method" in data and "id" not in data:
                method = data["method"]
                params = data.get("params", {})

                self.performance_metrics["notifications_received"] += 1

                # Call registered handlers
                if method in self.notification_handlers:
                    for handler in self.notification_handlers[method]:
                        try:
                            await handler(params)
                        except Exception as e:
                            logger.error(f"Error in notification handler for {method}: {e}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")


# Convenience functions for common operations

async def create_genesis_lsp_client(host: str = "localhost", port: int = 8080) -> GenesisLSPClient:
    """
    Create and connect Genesis LSP client.

    Args:
        host: Language server host
        port: Language server port

    Returns:
        Connected LSP client

    Raises:
        ConnectionError: If connection fails
    """
    client = GenesisLSPClient(host, port)

    if not await client.connect():
        raise ConnectionError(f"Failed to connect to Genesis Language Server at {host}:{port}")

    return client


async def validate_genesis_document(
    client: GenesisLSPClient,
    uri: str,
    content: str
) -> List[Dict[str, Any]]:
    """
    Validate Genesis document and get diagnostics.

    Args:
        client: Connected LSP client
        uri: Document URI
        content: Document content

    Returns:
        List of diagnostic issues
    """
    # Open document
    await client.did_open_document(uri, "genesis-yaml", 1, content)

    # Get diagnostics
    diagnostics = await client.get_diagnostics(uri)

    # Close document
    await client.did_close_document(uri)

    return diagnostics


if __name__ == "__main__":
    async def main():
        """Example usage of Genesis LSP client."""
        try:
            # Create and connect client
            client = await create_genesis_lsp_client()

            print("Connected to Genesis Language Server")

            # Example document
            document_uri = "file:///tmp/test.genesis.yaml"
            document_content = """
id: urn:agent:genesis:autonomize.ai:test:1.0.0
name: Test Agent
description: Test specification
agentGoal: Test goal
kind: Single Agent

components:
  input:
    type: genesis:chat_input
    name: User Input

  agent:
    type: genesis:agent
    name: Main Agent

  output:
    type: genesis:chat_output
    name: Response Output
"""

            # Validate document
            diagnostics = await validate_genesis_document(client, document_uri, document_content)

            print(f"Validation complete. Found {len(diagnostics)} issues:")
            for diagnostic in diagnostics:
                print(f"  - {diagnostic}")

            # Get performance metrics
            metrics = client.get_performance_metrics()
            print(f"Performance metrics: {metrics}")

            # Disconnect
            await client.disconnect()
            print("Disconnected from Genesis Language Server")

        except Exception as e:
            print(f"Error: {e}")

    # Run example
    asyncio.run(main())
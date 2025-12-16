import json
import logging
import os
import random
import time
import uuid
from http import HTTPStatus

from locust import HttpUser, between, events, task

logger = logging.getLogger(__name__)


@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument(
        "--project-id",
        type=str,
        default=os.getenv("PROJECT_ID", ""),
        help="Project ID for MCP server",
    )
    parser.add_argument(
        "--custom-headers",
        type=str,
        default="{}",
        help="JSON mapping of custom headers",
    )
    parser.add_argument(
        "--print-responses", action="store_true", help="Print full response bodies"
    )


class MCPProjectUser(HttpUser):
    """User for testing Langflow MCP Project Server."""

    # Dynamic wait time
    wait_time = between(
        float(os.getenv("MIN_WAIT", "1000")) / 1000,
        float(os.getenv("MAX_WAIT", "3000")) / 1000,
    )

    connection_timeout = float(os.getenv("REQUEST_TIMEOUT", "30.0"))

    def on_start(self):
        """Setup and validate required configurations."""
        self.project_id = self.environment.parsed_options.project_id
        if not self.project_id:
            logger.error("Missing --project-id argument")
            self.environment.runner.quit()
            return

        self.print_responses = self.environment.parsed_options.print_responses
        # Force log level to INFO if printing responses is requested
        if self.print_responses:
            logging.getLogger().setLevel(logging.INFO)

        # Parse custom headers
        custom_headers_str = self.environment.parsed_options.custom_headers
        try:
            self.custom_headers = json.loads(custom_headers_str)
        except json.JSONDecodeError:
            logger.exception("Invalid JSON for --custom-headers")
            self.custom_headers = {}

        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self.headers.update(self.custom_headers)

        self.session_id = f"locust_{uuid.uuid4()}"
        self.available_tools = []
        self.selected_tools = []

        # Fetch available tools
        self.fetch_tools()

        # Select 1-2 tools for this user to execute repeatedly
        if self.available_tools:
            # Use SystemRandom for secure random numbers to satisfy linter
            secure_random = random.SystemRandom()
            num_tools = min(len(self.available_tools), secure_random.randint(1, 2))
            self.selected_tools = secure_random.sample(self.available_tools, num_tools)
            logger.info(f"User selected tools: {[t['name'] for t in self.selected_tools]}")
        else:
            logger.warning("No tools available to execute.")

    def log_error(self, name: str, exc: Exception, response_time: float):
        """Helper method to log errors in a format Locust expects."""
        self.environment.stats.log_error("ERROR", name, str(exc))
        self.environment.stats.log_request("ERROR", name, response_time, 0)

    def fetch_tools(self):
        """Fetch list of tools from the MCP server."""
        endpoint = f"/api/v1/mcp/project/{self.project_id}/streamable"

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "locust-client", "version": "1.0.0"},
            },
        }

        if self.print_responses:
            logger.info(f"Fetching tools from {endpoint}")

        start_time = time.time()
        try:
            with self.client.post(
                endpoint,
                json=payload,
                headers=self.headers,
                catch_response=True,
                timeout=self.connection_timeout,
                stream=True
            ) as response:
                response_time = (time.time() - start_time) * 1000

                if response.status_code != HTTPStatus.OK:
                    response.failure(f"Failed to fetch tools: {response.status_code}")
                    return

                # Parse SSE response
                tools_found = False
                for line in response.iter_lines():
                    if not line:
                        continue

                    decoded_line = line.decode("utf-8")
                    if decoded_line.startswith("data: "):
                        json_str = decoded_line[6:]
                        try:
                            data = json.loads(json_str)
                            if "result" in data and "tools" in data["result"]:
                                self.available_tools = data["result"]["tools"]
                                tools_found = True
                                if self.print_responses:
                                    logger.info(f"Tools found: {len(self.available_tools)}")
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to decode JSON from SSE line: {decoded_line}")
                            self.log_error(endpoint, e, response_time)

                if not tools_found:
                    logger.warning("No tool list found in response")

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.exception("Exception during fetch_tools")
            self.log_error(endpoint, e, response_time)
            # We can't fail the response object here as it's out of context if the exception happened outside.
            # But the task will fail implicitly by exception.

    @task
    def run_tool(self):
        if not self.selected_tools:
            return

        secure_random = random.SystemRandom()
        tool = secure_random.choice(self.selected_tools)
        tool_name = tool["name"]

        # Determine arguments (currently empty as per sample)
        # Parse tool['inputSchema'] to generate valid args
        arguments = {}
        properties = tool.get("inputSchema", {}).get("properties", None)
        if properties is None:
            msg = "tool has invalid inputSchema"
            raise ValueError(msg)
        if "input_value" not in properties:
            msg = "only the 'input_value' flow input is supported for this cli"
            raise ValueError(msg)

        arguments["input_value"] = random.choice([ # noqa: S311
            "wow! good stuff!",
            "how are you?",
            "hi, can you help me?",
            "i'm sorry, i'm not sure i understand you",
            "i'm sorry, i'm not sure i can help you with that",
        ])

        endpoint = f"/api/v1/mcp/project/{self.project_id}/streamable"

        payload = {
            "jsonrpc": "2.0",
            "id": secure_random.randint(2, 10000),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
        }

        if self.print_responses:
            logger.info(f"Calling tool '{tool_name}' at {endpoint}")

        start_time = time.time()
        try:
            with self.client.post(
                endpoint,
                json=payload,
                headers=self.headers,
                catch_response=True,
                timeout=self.connection_timeout,
                stream=True
            ) as response:
                response_time = (time.time() - start_time) * 1000

                if response.status_code == HTTPStatus.OK:
                    # We need to read the stream to confirm success and get result
                    # Ideally we check for "result" in the JSON-RPC response
                    success = False
                    error_msg = ""
                    collected_response = []

                    # Using delimiter='\n' to ensure we get lines, though default is usually fine.
                    # chunk_size=None means it will yield chunks as they arrive, but iter_lines handles buffering.
                    for line in response.iter_lines():
                        if not line:
                            continue
                        decoded_line = line.decode("utf-8")
                        collected_response.append(decoded_line)
                        if decoded_line.startswith("data: "):
                            json_str = decoded_line[6:]
                            try:
                                data = json.loads(json_str)
                                # Check for JSON-RPC error
                                if "error" in data:
                                    error_msg = json.dumps(data["error"])
                                    break

                                # Check for result (successful execution)
                                if "result" in data:
                                    success = True
                            except json.JSONDecodeError as e:
                                self.log_error(endpoint, e, response_time)

                    if self.print_responses:
                        logger.info("[%s] Full Response:\n%s", tool_name, "\n".join(collected_response))

                    if success:
                        response.success()
                    else:
                        failure_msg = error_msg if error_msg else "No result in SSE stream"
                        response.failure(f"Tool execution failed: {failure_msg}")
                        self.log_error(endpoint, Exception(failure_msg), response_time)
                else:
                    error_text = response.text or "No response text"
                    error_msg = f"HTTP Error {response.status_code}: {error_text[:200]}"
                    response.failure(error_msg)
                    self.log_error(endpoint, Exception(error_msg), response_time)
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.log_error(endpoint, e, response_time)
            # Cannot call response.failure here as context is closed
            # But the task will fail implicitly by exception.


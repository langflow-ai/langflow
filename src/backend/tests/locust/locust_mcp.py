import json
import logging
import os
import random
import time
import uuid
from http import HTTPStatus

import requests
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


# Global storage for tools to be fetched once
GLOBAL_AVAILABLE_TOOLS = []


@events.test_start.add_listener
def fetch_global_tools(environment, **_kwargs):
    """Fetch tools once at the start of the test and store in global variable."""
    global GLOBAL_AVAILABLE_TOOLS

    logger.info("Initializing: Fetching global tools list...")

    project_id = environment.parsed_options.project_id
    if not project_id:
        logger.error("Missing --project-id argument, cannot fetch tools.")
        return

    # Parse custom headers just for this request
    custom_headers_str = environment.parsed_options.custom_headers
    try:
        custom_headers = json.loads(custom_headers_str)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON for --custom-headers during global fetch")
        custom_headers = {}

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    headers.update(custom_headers)

    # Ensure we have a host to make the request to
    host = environment.host
    if not host:
        logger.warning("No host specified in environment, skipping global tool fetch.")
        return

    # Handle potentially missing protocol in host or ensure it is clean
    if not host.startswith("http"):
        host = "http://" + host

    endpoint = f"{host}/api/v1/mcp/project/{project_id}/streamable"

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "locust-global-client", "version": "1.0.0"},
        },
    }

    try:
        # We use requests directly here since we don't need User stats for setup
        with requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=30.0,
            stream=True
        ) as response:
            if response.status_code != HTTPStatus.OK:
                logger.error(
                    f"Failed to fetch global tools: {response.status_code} - "
                    f"{response.text}"
                )
                return

            # Parse SSE response
            for line in response.iter_lines():
                if not line:
                    continue
                decoded_line = line.decode("utf-8")
                if not decoded_line.startswith("data: "):
                    continue

                try:
                    data = json.loads(decoded_line[6:])
                    if "result" in data and "tools" in data["result"]:
                        GLOBAL_AVAILABLE_TOOLS = data["result"]["tools"]
                        logger.info(f"Successfully fetched {len(GLOBAL_AVAILABLE_TOOLS)} tools globally.")
                        return
                except Exception:
                    logger.debug(
                        "Failed to parse SSE line during global fetch",
                        exc_info=True
                    )
                    continue

            if not GLOBAL_AVAILABLE_TOOLS:
                logger.warning("No tools found in global fetch response.")

    except Exception:
        logger.exception("Exception during global tool fetch")


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

        # Use the globally fetched tools
        self.available_tools = list(GLOBAL_AVAILABLE_TOOLS)
        self.selected_tools = []

        if not self.available_tools:
            logger.warning(
                "No global tools available. "
                "Retrying fetch or tools list is empty."
            )

        # Select 1-2 tools for this user to execute repeatedly
        if self.available_tools:
            # Use SystemRandom for secure random numbers to satisfy linter
            secure_random = random.SystemRandom()
            num_tools = min(
                len(self.available_tools),
                secure_random.randint(1, 2)
                )
            self.selected_tools = secure_random.sample(
                self.available_tools,
                num_tools
                )
            logger.debug(
                f"User selected tools: {[t['name'] for t in self.selected_tools]}"
            )
        else:
            logger.warning("No tools available to execute.")

    def log_error(self, name: str, exc: Exception, response_time: float):
        """Helper method to log errors in a format Locust expects."""
        self.environment.stats.log_error("ERROR", name, str(exc))
        self.environment.stats.log_request("ERROR", name, response_time, 0)

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
            "write a one-page essay about the benefits of using langflow",
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

        logger.debug(f"Calling tool '{tool_name}' at {endpoint}")

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
                    error_msg = (
                        f"HTTP Error {response.status_code}: "
                        f"{response.text or 'No response text'}"
                        )
                    response.failure(error_msg)
                    self.log_error(endpoint, Exception(error_msg), response_time)
                    return

                success = False
                error_msg = ""
                for line in response.iter_lines():
                    if not line:
                        continue

                    decoded_line = line.decode("utf-8")

                    if not decoded_line.startswith("data: "):
                        continue

                    try:
                        data = json.loads(decoded_line[6:])
                        logger.debug(
                            "[%s] Result Data:\n%s",
                            tool_name,
                            json.dumps(data, indent=2)
                            )
                        if "error" in data:
                            error_msg = json.dumps(data["error"])
                            break
                        if "result" in data: # note: the tool itself might fail
                            success = True
                    except Exception as e:
                        self.log_error(endpoint, e, response_time)

                if not success:
                    failure_msg = error_msg or "No result in stream response"
                    response.failure(f"Tool execution failed: {failure_msg}")
                    self.log_error(endpoint, Exception(failure_msg), response_time)
                    return

                response.success()
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.log_error(endpoint, e, response_time)

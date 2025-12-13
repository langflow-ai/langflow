"""MCP Server Stress Testing with Locust.

Tests both SSE and Streamable HTTP transports for MCP servers.

Usage:
    # Required
    export LF_TOKEN="your-langflow-token"

    # Optional - Environment
    export LF_PROJECT_ID="your-project-id"
    export LF_ORG="your-org-id"

    # Optional - Logging
    export PRINT_RESPONSES="true"  # Print response content for debugging

    # Optional - User Class Weights (0 to disable, higher = more of this type)
    export WEIGHT_STREAMABLE="3"  # MCPStreamableHTTPUser (list tools/resources)
    export WEIGHT_PROJECT="3"     # MCPProjectStreamableUser (project-specific)
    export WEIGHT_BURST="2"       # MCPBurstUser (burst traffic)
    export WEIGHT_CONCURRENT="2"  # MCPConcurrentSessionUser (concurrent ops)

    # Optional - Task Weights (0 to disable)
    export TASK_LIST_TOOLS="40"
    export TASK_LIST_RESOURCES="30"
    export TASK_CALL_TOOL="0"  # Agent execution - slow, disabled by default
    export TASK_PROJECT_LIST="50"
    export TASK_PROJECT_CALL="0"  # Project agent execution - slow

    # Optional - Wait Time Strategy
    export WAIT_TIME_MIN="0.1"     # Minimum wait between requests (seconds)
    export WAIT_TIME_MAX="0.5"     # Maximum wait between requests (seconds)
    export BURST_WAIT_MIN="1"      # Burst cycle minimum wait
    export BURST_WAIT_MAX="3"      # Burst cycle maximum wait
    export CONCURRENT_PACING="0.5" # Concurrent constant pacing (seconds)

    # Optional - Performance
    export REQUEST_TIMEOUT="30.0"  # Request timeout (increase for tool calls)

    locust -f mcp_locustfile.py --host http://localhost:7860

Examples:
    # Test primarily tool calls (slow, needs high timeout)
    export LF_TOKEN="token" TASK_CALL_TOOL="50" TASK_PROJECT_CALL="50" \
           TASK_LIST_TOOLS="10" TASK_LIST_RESOURCES="10" TASK_PROJECT_LIST="10" \
           REQUEST_TIMEOUT="120" WAIT_TIME_MIN="1" WAIT_TIME_MAX="3"
    locust -f mcp_locustfile.py -u 10 -r 2

    # Test list operations only (fast, high throughput)
    export LF_TOKEN="token" TASK_CALL_TOOL="0" TASK_PROJECT_CALL="0" \
           WAIT_TIME_MIN="0.1" WAIT_TIME_MAX="0.3"
    locust -f mcp_locustfile.py -u 250 -r 10

    # Test burst patterns
    export LF_TOKEN="token" WEIGHT_BURST="10" WEIGHT_STREAMABLE="1" \
           WEIGHT_PROJECT="1" WEIGHT_CONCURRENT="1"
    locust -f mcp_locustfile.py -u 50 -r 5
"""

import logging
import os

import gevent
from locust import HttpUser, LoadTestShape, between, constant_pacing, task

# Set up logger - logs will appear in Locust's Master Logs UI
logger = logging.getLogger(__name__)


# Configuration from environment variables
WEIGHT_STREAMABLE = int(os.getenv("WEIGHT_STREAMABLE", "3"))
WEIGHT_PROJECT = int(os.getenv("WEIGHT_PROJECT", "3"))
WEIGHT_BURST = int(os.getenv("WEIGHT_BURST", "2"))
WEIGHT_CONCURRENT = int(os.getenv("WEIGHT_CONCURRENT", "2"))

TASK_LIST_TOOLS = int(os.getenv("TASK_LIST_TOOLS", "40"))
TASK_LIST_RESOURCES = int(os.getenv("TASK_LIST_RESOURCES", "30"))
TASK_CALL_TOOL = int(os.getenv("TASK_CALL_TOOL", "0"))
TASK_PROJECT_LIST = int(os.getenv("TASK_PROJECT_LIST", "50"))
TASK_PROJECT_CALL = int(os.getenv("TASK_PROJECT_CALL", "0"))

WAIT_TIME_MIN = float(os.getenv("WAIT_TIME_MIN", "0.1"))
WAIT_TIME_MAX = float(os.getenv("WAIT_TIME_MAX", "0.5"))
BURST_WAIT_MIN = float(os.getenv("BURST_WAIT_MIN", "1"))
BURST_WAIT_MAX = float(os.getenv("BURST_WAIT_MAX", "3"))
CONCURRENT_PACING = float(os.getenv("CONCURRENT_PACING", "0.5"))


# MCP Protocol Messages
MCP_LIST_TOOLS_REQUEST = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {},
}

MCP_LIST_RESOURCES_REQUEST = {
    "jsonrpc": "2.0",
    "id": 3,
    "method": "resources/list",
    "params": {},
}


def make_call_tool_request(tool_name: str, arguments: dict, request_id: int = 4):
    """Create an MCP call_tool request."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }


class BaseMCPUser(HttpUser):
    """Base class for MCP stress testing users."""

    abstract = True
    REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "30.0"))
    host = os.getenv("LANGFLOW_HOST", "http://localhost:7860")

    def on_start(self):
        """Initialize user with credentials."""
        self.lf_token = os.getenv("LF_TOKEN")
        self.lf_project_id = os.getenv("LF_PROJECT_ID")
        self.lf_org = os.getenv("LF_ORG")
        self.print_responses = os.getenv("PRINT_RESPONSES", "false").lower() == "true"

        if not self.lf_token:
            raise ValueError("LF_TOKEN environment variable required")

        self.headers = {
            "Authorization": f"Bearer {self.lf_token}",
            "Content-Type": "application/json",
            "Accept": "application/json,text/event-stream",
        }

        # Add organization header if provided
        if self.lf_org:
            self.headers["X-DataStax-Current-Org"] = self.lf_org

        self.request_counter = 0

    def get_request_id(self):
        """Generate unique request ID."""
        self.request_counter += 1
        return self.request_counter


class MCPStreamableHTTPUser(BaseMCPUser):
    """Test Streamable HTTP transport for MCP servers."""

    weight = WEIGHT_STREAMABLE
    wait_time = between(WAIT_TIME_MIN, WAIT_TIME_MAX)

    @task(TASK_LIST_TOOLS)
    def list_tools(self):
        """List available MCP tools via Streamable HTTP."""
        endpoint = "/api/v1/mcp/streamable"
        request = {**MCP_LIST_TOOLS_REQUEST, "id": self.get_request_id()}

        with self.client.post(
            endpoint,
            json=request,
            headers=self.headers,
            name="[Streamable HTTP] tools/list",
            catch_response=True,
        ) as response:
            if self.print_responses:
                logger.info(f"[Streamable HTTP] tools/list Response ({response.status_code}): {response.text}")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(TASK_LIST_RESOURCES)
    def list_resources(self):
        """List MCP resources via Streamable HTTP."""
        endpoint = "/api/v1/mcp/streamable"
        request = {**MCP_LIST_RESOURCES_REQUEST, "id": self.get_request_id()}

        with self.client.post(
            endpoint,
            json=request,
            headers=self.headers,
            name="[Streamable HTTP] resources/list",
            catch_response=True,
        ) as response:
            if self.print_responses:
                logger.info(f"[Streamable HTTP] resources/list Response ({response.status_code}): {response.text}")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(TASK_CALL_TOOL)
    def call_tool(self):
        """Call an MCP tool via Streamable HTTP."""
        request = make_call_tool_request(
            tool_name="simple_agent_1",
            arguments={"input_value": "test message"},
            request_id=self.get_request_id(),
        )
        endpoint = "/api/v1/mcp/streamable"

        with self.client.post(
            endpoint,
            json=request,
            headers=self.headers,
            name="[Streamable HTTP] tools/call",
            catch_response=True,
            timeout=self.REQUEST_TIMEOUT,
        ) as response:
            if self.print_responses:
                logger.info(f"[Streamable HTTP] tools/call Response ({response.status_code}): {response.text}")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")


class MCPProjectStreamableUser(BaseMCPUser):
    """Test project-specific MCP servers via Streamable HTTP."""

    weight = WEIGHT_PROJECT
    wait_time = between(WAIT_TIME_MIN, WAIT_TIME_MAX)

    def on_start(self):
        super().on_start()
        if not self.lf_project_id:
            raise ValueError("LF_PROJECT_ID environment variable required")

    @task(TASK_PROJECT_LIST)
    def list_project_tools(self):
        """List tools for a specific project."""
        endpoint = f"/api/v1/mcp/project/{self.lf_project_id}/streamable"
        request = {**MCP_LIST_TOOLS_REQUEST, "id": self.get_request_id()}

        with self.client.post(
            endpoint,
            json=request,
            headers=self.headers,
            name="[Project Streamable] tools/list",
            catch_response=True,
        ) as response:
            if self.print_responses:
                logger.info(f"[Project Streamable] tools/list Response ({response.status_code}): {response.text}")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(TASK_PROJECT_CALL)
    def call_project_tool(self):
        """Execute a tool on project MCP server."""
        endpoint = f"/api/v1/mcp/project/{self.lf_project_id}/streamable"
        request = make_call_tool_request(
            tool_name="simple_agent_1",
            arguments={"input_value": "stress test message"},
            request_id=self.get_request_id(),
        )

        with self.client.post(
            endpoint,
            json=request,
            headers=self.headers,
            name="[Project Streamable] tools/call",
            catch_response=True,
            timeout=self.REQUEST_TIMEOUT,
        ) as response:
            if self.print_responses:
                logger.info(f"[Project Streamable] tools/call Response ({response.status_code}): {response.text}")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")


class MCPBurstUser(BaseMCPUser):
    """Simulate burst traffic patterns to test connection handling."""

    weight = WEIGHT_BURST
    wait_time = between(BURST_WAIT_MIN, BURST_WAIT_MAX)

    @task
    def burst_list_tools(self):
        """Send a burst of list_tools requests."""
        endpoint = "/api/v1/mcp/streamable"

        for i in range(10):
            request = {**MCP_LIST_TOOLS_REQUEST, "id": self.get_request_id()}
            with self.client.post(
                endpoint,
                json=request,
                headers=self.headers,
                name=f"[Burst] tools/list-{i}",
                catch_response=True,
            ) as response:
                if self.print_responses:
                    logger.info(f"[Burst] tools/list-{i} Response ({response.status_code}): {response.text}")
                if response.status_code != 200:
                    response.failure(f"HTTP {response.status_code}")
            gevent.sleep(0.05)


class MCPConcurrentSessionUser(BaseMCPUser):
    """Simulate multiple concurrent MCP sessions."""

    weight = WEIGHT_CONCURRENT
    wait_time = constant_pacing(CONCURRENT_PACING)

    @task
    def concurrent_operations(self):
        """Perform multiple operations in rapid succession."""
        endpoint = "/api/v1/mcp/streamable"

        with self.client.post(
            endpoint,
            json={**MCP_LIST_TOOLS_REQUEST, "id": self.get_request_id()},
            headers=self.headers,
            name="[Concurrent] tools/list",
            catch_response=True,
        ) as response:
            if self.print_responses:
                logger.info(f"[Concurrent] tools/list Response ({response.status_code}): {response.text}")

        with self.client.post(
            endpoint,
            json={**MCP_LIST_RESOURCES_REQUEST, "id": self.get_request_id()},
            headers=self.headers,
            name="[Concurrent] resources/list",
            catch_response=True,
        ) as response:
            if self.print_responses:
                logger.info(f"[Concurrent] resources/list Response ({response.status_code}): {response.text}")


# Uncomment the class below to enable automated load ramping.
# When commented out, you can control users, spawn rate, and RPS through the Locust UI.
#
# class MCPRampShape(LoadTestShape):
#     """Ramp users from 0 to target over time."""
#
#     stages = [
#         {"duration": 30, "users": 10, "spawn_rate": 2},
#         {"duration": 60, "users": 25, "spawn_rate": 5},
#         {"duration": 120, "users": 50, "spawn_rate": 5},
#         {"duration": 180, "users": 100, "spawn_rate": 10},
#         {"duration": 240, "users": 100, "spawn_rate": 10},
#     ]
#
#     def tick(self):
#         run_time = self.get_run_time()
#         for stage in self.stages:
#             if run_time < stage["duration"]:
#                 return stage["users"], stage["spawn_rate"]
#         return None

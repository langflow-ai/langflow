import json
import logging
import os
import random
import sys
import time
from http import HTTPStatus

from locust import FastHttpUser, between, events, task

logger = logging.getLogger(__name__)


@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument(
        "--flows",
        type=str,
        default="[]",
        help="JSON list of flow configs: [{name: str, id: str, input_value: list}]",
    )
    parser.add_argument("--custom-headers", type=str, default="{}", help="JSON mapping of custom headers")
    parser.add_argument("--print-responses", action="store_true", help="Print full response bodies")


@events.quitting.add_listener
def _(environment, **_kwargs):
    """Print stats at test end for analysis."""
    if environment.stats.total.fail_ratio > 0.01:
        environment.process_exit_code = 1
    environment.runner.quit()


class BaseFlowUser(FastHttpUser):
    """Base user for flow stress testing."""

    abstract = True
    flow_name: str = "Unknown Flow"
    flow_id: str = ""
    input_values: list[str] = ["Hello"]

    # Dynamic wait time based on environment variables or defaults
    wait_time = between(
        float(os.getenv("MIN_WAIT", "1000")) / 1000,
        float(os.getenv("MAX_WAIT", "3000")) / 1000,
    )

    connection_timeout = float(os.getenv("REQUEST_TIMEOUT", "30.0"))

    def on_start(self):
        """Setup and validate required configurations."""
        if not hasattr(self, "session_id"):
            import uuid
            self.session_id = f"locust_{uuid.uuid4()}"

        self._last_response: dict | None = None

        # Parse CLI options for logging and headers
        self.print_responses = self.environment.parsed_options.print_responses

        custom_headers_str = self.environment.parsed_options.custom_headers
        try:
            self.custom_headers = json.loads(custom_headers_str)
        except json.JSONDecodeError:
            logger.exception("Invalid JSON for --custom-headers")
            self.custom_headers = {}

        # Merge custom headers (including auth)
        self.headers = self.custom_headers.copy()

        # Validate Flow ID
        if not self.flow_id:
            # Fallback: check env var if this looks like a legacy run
            if self.flow_name == "Legacy Flow":
                self.flow_id = os.getenv("FLOW_ID", "")

            if not self.flow_id:
                logger.error(f"Missing flow ID for {self.flow_name}")
        elif self.print_responses:
            logger.info(f"User for '{self.flow_name}' initialized with Flow ID: {self.flow_id}")

        # Basic health check
        with self.client.get("/health", headers=self.headers, catch_response=True) as response:
            if response.status_code != HTTPStatus.OK:
                logger.warning(f"Initial health check failed: {response.status_code}")

    def log_error(self, name: str, exc: Exception, response_time: float):
        """Helper method to log errors in a format Locust expects."""
        self.environment.stats.log_error("ERROR", name, str(exc))
        self.environment.stats.log_request("ERROR", name, response_time, 0)

    def get_input_value(self):
        """Selects a random input value from the configured list."""
        if not self.input_values:
            return "Hello"
        return random.choice(self.input_values)

    @task(1)
    def run_flow_endpoint(self):
        """Sends a POST request to the run endpoint using a realistic payload."""
        if not self.flow_id:
            logger.error(f"Skipping task for {self.flow_name} due to missing flow ID")
            return

        endpoint = f"/api/v1/run/{self.flow_id}?stream=false"

        # Get dynamic input value
        input_val = self.get_input_value()

        payload = {
            "input_value": input_val,
            "output_type": "chat",
            "input_type": "chat",
            "tweaks": {},
            "session_id": self.session_id,
        }

        # Combine default headers with custom headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        headers.update(self.headers)

        if self.print_responses:
            logger.info(f"[{self.flow_name}] Request to {endpoint} with payload: {json.dumps(payload)}")

        start_time = time.time()
        try:
            with self.client.post(
                endpoint, json=payload, headers=headers, catch_response=True, timeout=self.connection_timeout
            ) as response:
                response_time = (time.time() - start_time) * 1000

                if self.print_responses:
                    logger.info(f"[{self.flow_name}] Response ({response.status_code}): {response.text}")

                if response.status_code == HTTPStatus.OK:
                    try:
                        self._last_response = response.json()
                    except ValueError as e:
                        response.failure("Invalid JSON response")
                        self.log_error(endpoint, e, response_time)
                else:
                    error_text = response.text or "No response text"
                    error_msg = f"Unexpected status code: {response.status_code}, Response: {error_text[:200]}"
                    response.failure(error_msg)
                    self.log_error(endpoint, Exception(error_msg), response_time)
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.log_error(endpoint, e, response_time)
            response.failure(f"Error: {e}")


def _create_dynamic_users():
    """Parses CLI args manually to register User classes before Locust starts."""
    flows_arg = "[]"

    # Manual argv parsing to find --flows
    # We do this because we need to define the classes at module level
    # before the Locust environment is fully initialized.
    for i, arg in enumerate(sys.argv):
        if arg.startswith("--flows="):
            flows_arg = arg.split("=", 1)[1]
            break
        if arg == "--flows" and i + 1 < len(sys.argv):
            flows_arg = sys.argv[i + 1]
            break

    try:
        flows_list = json.loads(flows_arg)
    except json.JSONDecodeError:
        logger.exception("Failed to parse --flows JSON for dynamic user generation")
        flows_list = []

    # If no flows provided but we have legacy env vars, create a default user
    if not flows_list and os.getenv("FLOW_ID"):
        flows_list.append({
            "name": "Legacy Flow",
            "id": os.getenv("FLOW_ID"),
            "input_value": ["Hello"],
        })

    for flow_config in flows_list:
        name = flow_config.get("name", "Unknown")
        # Sanitize name for Python class
        safe_name = "".join(x for x in name.title() if x.isalnum()) + "User"

        attributes = {
            "flow_name": name,
            "flow_id": flow_config.get("id"),
            "input_values": flow_config.get("input_value", ["Hello"]),
            "abstract": False,  # Make it runnable
        }

        # Dynamically create the class
        user_class = type(safe_name, (BaseFlowUser,), attributes)
        logger.info(f"Created user class: {safe_name}")

        # Register in global scope so Locust finds it
        globals()[safe_name] = user_class


# Run dynamic generation
_create_dynamic_users()

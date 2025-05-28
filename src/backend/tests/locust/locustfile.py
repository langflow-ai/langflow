import os
import time
from http import HTTPStatus

from locust import FastHttpUser, between, events, task


@events.quitting.add_listener
def _(environment, **_kwargs):
    """Print stats at test end for analysis."""
    if environment.stats.total.fail_ratio > 0.01:
        environment.process_exit_code = 1
    environment.runner.quit()


class FlowRunUser(FastHttpUser):
    """FlowRunUser simulates users sending requests to the Langflow run endpoint.

    Designed for high-load testing with proper wait times and connection handling.
    Uses FastHttpUser for better performance with keep-alive connections and connection pooling.

    Environment Variables:
      - LANGFLOW_HOST: Base URL for the Langflow server (default: http://localhost:7860)
      - FLOW_ID: UUID or endpoint name of the flow to test (default: 62c21279-f7ca-43e2-b5e3-326ac573db04)
      - API_KEY: API key for authentication, sent as header 'x-api-key' (Required)
      - MIN_WAIT: Minimum wait time between requests in ms (default: 2000)
      - MAX_WAIT: Maximum wait time between requests in ms (default: 5000)
      - REQUEST_TIMEOUT: Timeout for each request in seconds (default: 30.0)
    """

    abstract = False  # This user class can be instantiated
    connection_timeout = float(os.getenv("REQUEST_TIMEOUT", "30.0"))  # Configurable timeout
    network_timeout = float(os.getenv("REQUEST_TIMEOUT", "30.0"))

    # Dynamic wait time based on environment variables or defaults
    # Increased default minimum wait to reduce database pressure
    wait_time = between(
        float(os.getenv("MIN_WAIT", "2000")) / 1000,
        float(os.getenv("MAX_WAIT", "5000")) / 1000,
    )

    # Use the host provided by environment variable or default
    host = os.getenv("LANGFLOW_HOST", "http://localhost:7860")

    # Flow ID from environment variable or default example UUID
    flow_id = os.getenv("FLOW_ID")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._last_response: dict | None = None
        self._consecutive_failures = 0

    def on_start(self):
        """Setup and validate required configurations."""
        if not os.getenv("API_KEY"):
            msg = "API_KEY environment variable is required for load testing"
            raise ValueError(msg)

        # Test connection and auth before starting
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code != HTTPStatus.OK:
                msg = f"Initial health check failed: {response.status_code}"
                raise ConnectionError(msg)

    def log_error(self, name: str, exc: Exception, response_time: float):
        """Helper method to log errors in a format Locust expects.

        Args:
            name: The name/endpoint of the request
            exc: The exception that occurred
            response_time: The response time in milliseconds
        """
        # Log error in stats
        self.environment.stats.log_error("ERROR", name, str(exc))
        # Log request with error
        self.environment.stats.log_request("ERROR", name, response_time, 0)

    @task(1)
    def run_flow_endpoint(self):
        """Sends a POST request to the run endpoint using a realistic payload.

        Includes basic error handling.
        """
        if not self.flow_id:
            msg = "FLOW_ID environment variable is required for load testing"
            raise ValueError(msg)
        endpoint = f"/api/v1/run/{self.flow_id}?stream=false"

        # Realistic payload that exercises the system
        payload = {
            "input_value": (
                "Hey, Could you check https://docs.langflow.org for me? Later, could you calculate 1390 / 192 ?"
            ),
            "output_type": "chat",
            "input_type": "chat",
            "tweaks": {},
        }

        headers = {
            "Content-Type": "application/json",
            "x-api-key": os.getenv("API_KEY"),
            "Accept": "application/json",
        }

        start_time = time.time()
        try:
            with self.client.post(
                endpoint, json=payload, headers=headers, catch_response=True, timeout=self.connection_timeout
            ) as response:
                response_time = (time.time() - start_time) * 1000
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
        except Exception as e:  # noqa: BLE001
            response_time = (time.time() - start_time) * 1000
            self.log_error(endpoint, e, response_time)
            response.failure(f"Error: {e}")

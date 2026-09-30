"""Langflow API Locust Load Testing File.

Comprehensive load testing for Langflow API with multiple user behaviors and performance analysis.
Based on production-ready patterns with proper error handling, metrics tracking, and reporting.

Usage:
    # Run with web UI (recommended)
    locust -f locustfile.py --host http://localhost:7860

    # Run headless with built-in shape
    locust -f locustfile.py --host http://localhost:7860 --headless --shape RampToHundred

    # Run distributed (master)
    locust -f locustfile.py --host http://localhost:7860 --master

    # Run distributed (worker)
    locust -f locustfile.py --host http://localhost:7860 --worker --master-host=localhost

Environment Variables:
    - LANGFLOW_HOST: Base URL for the Langflow server (default: http://localhost:7860)
    - FLOW_ID: Flow ID to test (required)
    - API_KEY: API key for authentication (required)
    - MIN_WAIT: Minimum wait time between requests in ms (default: 2000)
    - MAX_WAIT: Maximum wait time between requests in ms (default: 5000)
    - REQUEST_TIMEOUT: Request timeout in seconds (default: 30.0)
    - SHAPE: Load test shape to use (default: none, options: ramp100, stepramp)
"""

import inspect
import json
import logging
import os
import random
import time
import traceback
from datetime import datetime
from pathlib import Path

import gevent
from locust import FastHttpUser, LoadTestShape, between, constant, constant_pacing, events, task

# Test messages with realistic distribution
TEST_MESSAGES = {
    "minimal": "Hi",
    "simple": "Can you help me?",
    "medium": "I need help understanding how machine learning works in this context.",
    "complex": "Please analyze this data: " + "x" * 500 + " and provide detailed insights.",
    "large": "Here's a complex scenario: " + "data " * 1000,
    "realistic": "Hey, Could you check https://docs.langflow.org for me? Later, could you calculate 1390 / 192 ?",
}

# Weighted message distribution for realistic load
MESSAGE_WEIGHTS = [("simple", 40), ("realistic", 25), ("medium", 20), ("minimal", 10), ("complex", 4), ("large", 1)]

# Enhanced error logging setup
ERROR_LOG_FILE = None
LANGFLOW_LOG_FILE = None
DETAILED_ERRORS = []


def setup_error_logging():
    """Set up detailed error logging for the load test."""
    global ERROR_LOG_FILE, LANGFLOW_LOG_FILE

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create detailed error log
    ERROR_LOG_FILE = f"langflow_load_test_detailed_errors_{timestamp}.log"

    # Set up error logger
    error_logger = logging.getLogger("langflow_load_test_errors")
    error_logger.setLevel(logging.DEBUG)

    # Create file handler
    error_handler = logging.FileHandler(ERROR_LOG_FILE)
    error_handler.setLevel(logging.DEBUG)

    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    error_handler.setFormatter(formatter)

    error_logger.addHandler(error_handler)

    # Try to capture Langflow logs
    langflow_log_paths = ["langflow.log", "logs/langflow.log", "../../../langflow.log", "../../../../langflow.log"]

    for log_path in langflow_log_paths:
        if Path(log_path).exists():
            LANGFLOW_LOG_FILE = log_path
            break

    print("📝 Error logging setup:")
    print(f"   • Detailed errors: {ERROR_LOG_FILE}")
    if LANGFLOW_LOG_FILE:
        print(f"   • Langflow logs: {LANGFLOW_LOG_FILE}")
    else:
        print("   • Langflow logs: Not found (will monitor common locations)")


def log_detailed_error(
    user_class, method, url, status_code, response_text, exception=None, request_data=None, traceback=None
):
    """Log detailed error information."""
    global DETAILED_ERRORS

    error_logger = logging.getLogger("langflow_load_test_errors")

    error_info = {
        "timestamp": datetime.now().isoformat(),
        "user_class": user_class,
        "method": method,
        "url": url,
        "status_code": status_code,
        "response_text": response_text[:1000] if response_text else None,  # Limit response size
        "request_data": request_data,
        "exception": str(exception) if exception else None,
        "traceback": traceback if traceback else None,
    }

    DETAILED_ERRORS.append(error_info)

    # Log to file
    error_logger.error(f"""
=== LOAD TEST ERROR ===
User Class: {user_class}
Method: {method}
URL: {url}
Status Code: {status_code}
Request Data: {json.dumps(request_data, indent=2) if request_data else "None"}
Response Text: {response_text[:500] if response_text else "None"}...
Exception: {exception}
Traceback: {traceback.format_exc() if exception else "None"}
========================
""")


def save_error_summary():
    """Save a summary of all errors encountered during the test."""
    if not DETAILED_ERRORS:
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_file = f"langflow_load_test_error_summary_{timestamp}.json"

    # Group errors by type
    error_summary = {}
    for error in DETAILED_ERRORS:
        key = f"{error['status_code']}_{error['user_class']}"
        if key not in error_summary:
            error_summary[key] = {
                "count": 0,
                "examples": [],
                "status_code": error["status_code"],
                "user_class": error["user_class"],
            }

        error_summary[key]["count"] += 1
        if len(error_summary[key]["examples"]) < 3:  # Keep up to 3 examples
            error_summary[key]["examples"].append(error)

    # Save summary
    with open(summary_file, "w") as f:
        json.dump(
            {
                "test_timestamp": timestamp,
                "total_errors": len(DETAILED_ERRORS),
                "error_types": len(error_summary),
                "error_breakdown": error_summary,
            },
            f,
            indent=2,
        )

    print(f"📊 Error summary saved: {summary_file}")


def capture_langflow_logs():
    """Capture recent Langflow logs if available."""
    if not LANGFLOW_LOG_FILE or not Path(LANGFLOW_LOG_FILE).exists():
        return None

    try:
        # Read last 1000 lines of Langflow log
        with open(LANGFLOW_LOG_FILE) as f:
            lines = f.readlines()
            recent_lines = lines[-1000:] if len(lines) > 1000 else lines

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        captured_log_file = f"langflow_server_logs_during_test_{timestamp}.log"

        with open(captured_log_file, "w") as f:
            f.write("# Langflow server logs captured during load test\n")
            f.write(f"# Original log file: {LANGFLOW_LOG_FILE}\n")
            f.write(f"# Capture time: {datetime.now().isoformat()}\n")
            f.write(f"# Lines captured: {len(recent_lines)}\n\n")
            f.writelines(recent_lines)

        print(f"📋 Langflow logs captured: {captured_log_file}")
        return captured_log_file

    except Exception as e:
        print(f"⚠️  Could not capture Langflow logs: {e}")
        return None


# Load test shapes
class RampToHundred(LoadTestShape):
    """0 -> 100 users at 5 users/sec (20s ramp), then hold until 180s total.

    Matches production testing patterns: 3 minutes, ramping to 100 users.
    """

    spawn_rate = 5
    target_users = 100
    total_duration = 180  # seconds

    def tick(self):
        run_time = self.get_run_time()
        if run_time >= self.total_duration:
            return None
        users = min(int(run_time * self.spawn_rate), self.target_users)
        return users, self.spawn_rate


class StepRamp(LoadTestShape):
    """Step ramp for finding performance cliffs.

    Steps every 30 seconds: 5 -> 10 -> 15 -> 20 -> 25 -> 30 -> 35 users.
    Each step holds for exactly 30 seconds to measure steady-state performance.
    """

    def tick(self):
        run_time = self.get_run_time()

        # Define the step progression with 30-second intervals
        steps = [
            (30, 5),  # 0-30s: 5 users
            (60, 10),  # 30-60s: 10 users
            (90, 15),  # 60-90s: 15 users
            (120, 20),  # 90-120s: 20 users
            (150, 25),  # 120-150s: 25 users
            (180, 30),  # 150-180s: 30 users
            (210, 35),  # 180-210s: 35 users
            (240, 40),  # 210-240s: 40 users
            (270, 45),  # 240-270s: 45 users
            (300, 50),  # 270-300s: 50 users
        ]

        # Find current step
        for time_limit, user_count in steps:
            if run_time < time_limit:
                return user_count, 10  # Fast spawn rate for quick transitions

        return None  # End test after 300 seconds


# Environment-scoped metrics tracking
_env_bags = {}


@events.test_start.add_listener
def on_test_start(environment, **_kwargs):
    """Initialize per-environment metrics tracking."""
    # Set up enhanced error logging
    setup_error_logging()

    _env_bags[environment] = {
        "slow_10s": 0,
        "slow_20s": 0,
    }


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):  # noqa: ARG001
    """Track slow requests using Locust's built-in timing."""
    # response_time is in milliseconds from Locust
    bag = _env_bags.get(context.get("environment") if context else None)
    if bag is None:
        # fallback: try the single environment we likely have
        if len(_env_bags) == 1:
            bag = next(iter(_env_bags.values()))
        else:
            return

    if exception is None:  # Only count successful requests for timing
        if response_time > 10_000:  # 10 seconds in ms
            bag["slow_10s"] += 1
        if response_time > 20_000:  # 20 seconds in ms
            bag["slow_20s"] += 1


@events.test_stop.add_listener
def on_test_stop(environment, **_kwargs):
    """Print comprehensive test summary with performance grading."""
    stats = environment.stats.total
    if stats.num_requests == 0:
        return

    # Get percentiles and basic stats
    p50 = stats.get_response_time_percentile(0.50) or 0
    p95 = stats.get_response_time_percentile(0.95) or 0
    p99 = stats.get_response_time_percentile(0.99) or 0
    fail_ratio = stats.fail_ratio
    current_rps = getattr(stats, "current_rps", 0.0)

    # Get slow request counts
    bag = _env_bags.get(environment, {"slow_10s": 0, "slow_20s": 0})

    # Performance grading based on production criteria
    grade = "A"
    issues = []

    if fail_ratio > 0.01:
        grade = "B"
        issues.append(f"fail {fail_ratio:.1%}")
    if fail_ratio > 0.05:
        grade = "C"
    if p95 > 10_000:
        grade = max(grade, "D")
        issues.append(f"p95 {p95 / 1000:.1f}s")
    if p95 > 20_000:
        grade = "F"
        issues.append(f"p95 {p95 / 1000:.1f}s")

    print(f"\n{'=' * 60}")
    print(f"LANGFLOW API LOAD TEST RESULTS - GRADE: {grade}")
    print(f"{'=' * 60}")
    print(f"Requests: {stats.num_requests:,} | Failures: {stats.num_failures:,} ({fail_ratio:.1%})")
    print(f"Response Times: p50={p50 / 1000:.2f}s p95={p95 / 1000:.2f}s p99={p99 / 1000:.2f}s")
    print(f"RPS: {current_rps:.1f} | Slow requests: >10s={bag['slow_10s']} >20s={bag['slow_20s']}")

    if issues:
        print(f"Issues: {', '.join(issues)}")

    # Production readiness assessment
    if grade in ["A", "B"]:
        print("✅ PRODUCTION READY - Performance meets production standards")
    elif grade == "C":
        print("⚠️  CAUTION - Acceptable but monitor closely in production")
    else:
        print("❌ NOT PRODUCTION READY - Significant performance issues detected")

    print(f"{'=' * 60}\n")

    # Save detailed error information
    save_error_summary()

    # Capture Langflow logs
    capture_langflow_logs()

    # Set exit code for CI/CD
    if fail_ratio > 0.01:
        environment.process_exit_code = 1

    # Cleanup
    _env_bags.pop(environment, None)


class BaseLangflowUser(FastHttpUser):
    """Base class for all Langflow API load testing user types."""

    abstract = True
    REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "30.0"))

    # Use the host provided by environment variable or default
    host = os.getenv("LANGFLOW_HOST", "http://localhost:7860")

    def on_start(self):
        """Called when a user starts before any task is scheduled."""
        # Get credentials from environment variables
        self.api_key = os.getenv("API_KEY")
        self.flow_id = os.getenv("FLOW_ID")

        if not self.api_key:
            raise ValueError("API_KEY environment variable is required. Run setup_langflow_test.py first.")

        if not self.flow_id:
            raise ValueError("FLOW_ID environment variable is required. Run setup_langflow_test.py first.")

        self.session_id = f"locust_{self.__class__.__name__}_{id(self)}_{int(time.time())}"
        self.request_count = 0

        # Test connection and auth
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code != 200:
                raise ConnectionError(f"Health check failed: {response.status_code}")

    def make_request(self, message_type="simple", tag_suffix=""):
        """Make a request with proper error handling and timing."""
        message = TEST_MESSAGES.get(message_type, TEST_MESSAGES["simple"])

        # Langflow API payload structure
        payload = {
            "input_value": message,
            "output_type": "chat",
            "input_type": "chat",
            "tweaks": {},
        }

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        self.request_count += 1
        endpoint = f"/api/v1/run/{self.flow_id}?stream=false"
        name = f"{endpoint} [{message_type}{tag_suffix}]"

        try:
            with self.client.post(
                endpoint,
                json=payload,
                headers=headers,
                name=name,
                timeout=self.REQUEST_TIMEOUT,
                catch_response=True,
            ) as response:
                # Get response text for error logging
                try:
                    response_text = response.text
                except Exception:
                    response_text = "Could not read response text"

                # Handle successful responses
                if response.status_code == 200:
                    try:
                        data = response.json()
                        # Langflow API success check - look for outputs
                        if data.get("outputs"):
                            return response.success()
                        # Check for error messages in the response
                        error_msg = data.get("detail", "Unknown error")

                        # Log detailed error for successful HTTP but failed flow execution
                        log_detailed_error(
                            user_class=self.__class__.__name__,
                            method="POST",
                            url=f"{self.host}{endpoint}",
                            status_code=response.status_code,
                            response_text=response_text,
                            request_data=payload,
                            exception=None,
                        )

                        return response.failure(f"Flow execution failed: {error_msg}")
                    except json.JSONDecodeError as e:
                        log_detailed_error(
                            user_class=self.__class__.__name__,
                            method="POST",
                            url=f"{self.host}{endpoint}",
                            status_code=response.status_code,
                            response_text=response_text,
                            request_data=payload,
                            exception=e,
                        )
                        return response.failure("Invalid JSON response")

                # Log all error responses with detailed information
                log_detailed_error(
                    user_class=self.__class__.__name__,
                    method="POST",
                    url=f"{self.host}{endpoint}",
                    status_code=response.status_code,
                    response_text=response_text,
                    request_data=payload,
                    exception=None,
                )

                # Handle specific error cases
                if response.status_code in (429, 503):
                    return response.failure(f"Backpressure/capacity: {response.status_code}")
                if response.status_code == 401:
                    return response.failure("Unauthorized - API key issue")
                if response.status_code == 404:
                    return response.failure("Flow not found - check FLOW_ID")
                if response.status_code >= 500:
                    return response.failure(f"Server error {response.status_code}")

                return response.failure(f"HTTP {response.status_code}")

        except Exception as e:
            # Get more detailed error information
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "is_timeout": "timeout" in str(e).lower(),
                "is_connection_error": "connection" in str(e).lower(),
                "is_dns_error": "name resolution" in str(e).lower() or "dns" in str(e).lower(),
            }

            # Log any exceptions that occur during the request
            log_detailed_error(
                user_class=self.__class__.__name__,
                method="POST",
                url=f"{self.host}{endpoint}",
                status_code=0,  # Connection error
                response_text=f"Connection Error: {error_details}",
                request_data=payload,
                exception=str(e),
                traceback=traceback.format_exc(),
            )
            # Re-raise the exception so Locust can handle it properly
            raise


class NormalUser(BaseLangflowUser):
    """Normal user simulating typical API interactions."""

    weight = 3
    wait_time = between(0.5, 2)  # Typical user think time

    @task(80)
    def send_message(self):
        """Main task: Send a message with weighted distribution."""
        message_type = random.choices([w[0] for w in MESSAGE_WEIGHTS], weights=[w[1] for w in MESSAGE_WEIGHTS], k=1)[0]  # noqa: S311
        self.make_request(message_type=message_type)

    @task(15)
    def send_burst(self):
        """Send a burst of 3 small messages quickly."""
        for i in range(3):
            self.make_request(message_type="minimal", tag_suffix=f"-burst{i}")
            gevent.sleep(0.1)  # Small delay between burst requests

    @task(5)
    def send_complex(self):
        """Occasionally send complex requests that stress the system."""
        self.make_request(message_type="complex")


class AggressiveUser(BaseLangflowUser):
    """Aggressive user with minimal wait times."""

    weight = 3
    wait_time = between(0.1, 0.3)  # Very aggressive

    @task
    def rapid_fire(self):
        """Send requests as fast as possible."""
        self.make_request(message_type="simple", tag_suffix="-rapid")


class SustainedLoadUser(BaseLangflowUser):
    """Maintains exactly 1 request/second for steady load testing."""

    weight = 3
    wait_time = constant_pacing(1)  # Exactly 1 request per second per user

    @task
    def steady_load(self):
        """Send requests at constant 1 RPS per user."""
        self.make_request(message_type="medium", tag_suffix="-steady")


class TailLatencyHunter(BaseLangflowUser):
    """Mixed workload designed to expose tail latency issues."""

    weight = 3
    wait_time = between(0.8, 1.5)

    @task
    def hunt_tail_latency(self):
        """Alternate between simple and complex requests to find tail latency."""
        if random.random() < 0.7:  # noqa: S311
            self.make_request(message_type="simple", tag_suffix="-tail")
        else:
            self.make_request(message_type="large", tag_suffix="-tail-heavy")


class ScalabilityTestUser(BaseLangflowUser):
    """Tests for scalability limits."""

    weight = 3
    wait_time = constant(1.0)  # Constant load to test scaling

    @task
    def scalability_test(self):
        """Send medium complexity requests to test scaling limits."""
        self.make_request(message_type="medium", tag_suffix="-scale")


class BurstUser(BaseLangflowUser):
    """Sends bursts of requests to test connection pooling."""

    weight = 3
    wait_time = between(5, 10)  # Long wait between bursts

    @task
    def burst_attack(self):
        """Send a burst of 10 requests quickly to test connection handling."""
        for i in range(10):
            self.make_request(message_type="minimal", tag_suffix=f"-burst{i}")
            gevent.sleep(0.05)  # 50ms between requests in burst


# Legacy user class for backward compatibility
class FlowRunUser(NormalUser):
    """Legacy FlowRunUser - now inherits from NormalUser for backward compatibility."""


# Auto-select shape based on environment variable
_shape_env = os.getenv("SHAPE", "").lower()
_selected = None

if _shape_env == "stepramp":
    _selected = StepRamp
elif _shape_env == "ramp100":
    _selected = RampToHundred

if _selected:
    # Create a single exported shape class and remove others so Locust sees only one
    SelectedLoadTestShape = type("SelectedLoadTestShape", (_selected,), {})
    globals()["SelectedLoadTestShape"] = SelectedLoadTestShape

    # Remove other shape classes so Locust auto-picks the selected one
    for _name, _obj in list(globals().items()):
        if (
            inspect.isclass(_obj)
            and issubclass(_obj, LoadTestShape)
            and _obj is not SelectedLoadTestShape
            and _obj is not LoadTestShape
        ):
            del globals()[_name]

"""LFX Locust Load Testing File.

Based on the weakness-focused stress test scripts with additional user behaviors.
Includes production-ready fixes for timing, error handling, and reporting.

This file tests the LFX API (complex serve), not the Langflow API.

Usage:
    # Run with web UI (recommended)
    locust -f locustfile_complex_serve.py --host http://127.0.0.1:8000

    # Run headless with built-in shape
    locust -f locustfile_complex_serve.py --host http://127.0.0.1:8000 --headless --shape RampToHundred

    # Run distributed (master)
    locust -f locustfile_complex_serve.py --host http://127.0.0.1:8000 --master

    # Run distributed (worker)
    locust -f locustfile_complex_serve.py --host http://127.0.0.1:8000 --worker --master-host=localhost

Environment Variables:
    - FLOW_ID: Flow ID to test (default: 5523731d-5ef3-56de-b4ef-59b0a224fdbc)
    - API_KEY: API key for authentication (default: test)
    - REQUEST_TIMEOUT: Request timeout in seconds (default: 10)
    - SHAPE: Load test shape to use (default: none, options: ramp100)
"""

import inspect
import json
import os
import random
import time

import gevent
from locust import FastHttpUser, LoadTestShape, between, constant, constant_pacing, events, task

# Configuration
FLOW_ID = os.getenv("FLOW_ID", "5523731d-5ef3-56de-b4ef-59b0a224fdbc")
API_KEY = os.getenv("API_KEY", "test")
API_ENDPOINT = f"/flows/{FLOW_ID}/run"

# Test messages with realistic distribution
TEST_MESSAGES = {
    "minimal": "Hi",
    "simple": "Can you help me?",
    "medium": "I need help understanding how machine learning works in this context.",
    "complex": "Please analyze this data: " + "x" * 500 + " and provide detailed insights.",
    "large": "Here's a complex scenario: " + "data " * 1000,
}

# Weighted message distribution for realistic load
MESSAGE_WEIGHTS = [("simple", 50), ("medium", 30), ("minimal", 15), ("complex", 4), ("large", 1)]


# Load test shapes
class RampToHundred(LoadTestShape):
    """0 -> 100 users at 5 users/sec (20s ramp), then hold until 180s total.

    Matches the TLDR test pattern: 3 minutes, ramping to 100 users.
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


# Environment-scoped metrics tracking (fixes the event listener issue)
_env_bags = {}


@events.test_start.add_listener
def on_test_start(environment, **_kwargs):
    """Initialize per-environment metrics tracking."""
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
    stats.get_response_time_percentile(0.50) or 0
    p95 = stats.get_response_time_percentile(0.95) or 0
    stats.get_response_time_percentile(0.99) or 0
    fail_ratio = stats.fail_ratio
    getattr(stats, "current_rps", 0.0)

    # Get slow request counts
    _env_bags.get(environment, {"slow_10s": 0, "slow_20s": 0})

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

    # Production readiness assessment
    if grade in ["A", "B"] or grade == "C":
        pass
    else:
        pass

    # Cleanup
    _env_bags.pop(environment, None)


class BaseLfxUser(FastHttpUser):
    """Base class for all LFX API load testing user types."""

    abstract = True
    REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "10"))  # Tighter timeout for production

    def on_start(self):
        """Called when a user starts before any task is scheduled."""
        self.session_id = f"locust_{self.__class__.__name__}_{id(self)}_{int(time.time())}"
        self.request_count = 0

    def make_request(self, message_type="simple", tag_suffix=""):
        """Make a request with proper error handling and timing.

        Uses Locust's built-in response time measurement.
        """
        message = TEST_MESSAGES.get(message_type, TEST_MESSAGES["simple"])

        payload = {"input_value": message, "session_id": f"{self.session_id}_{self.request_count}"}

        headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}

        self.request_count += 1
        name = f"{API_ENDPOINT} [{message_type}{tag_suffix}]"

        with self.client.post(
            API_ENDPOINT,
            json=payload,
            headers=headers,
            name=name,
            timeout=self.REQUEST_TIMEOUT,
            catch_response=True,
        ) as response:
            # Handle successful responses
            if response.status_code == 200:
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    return response.failure("Invalid JSON response")

                # Strictly check for success=True in the response payload
                success = data.get("success")
                if success is True:
                    return response.success()

                # Application-level failure - success is False, None, or missing
                msg = str(data.get("result", "Unknown error"))[:200]
                success_status = f"success={success}" if success is not None else "success=missing"
                return response.failure(f"Flow failed ({success_status}): {msg}")

            # Handle specific error cases for better monitoring
            if response.status_code in (429, 503):
                return response.failure(f"Backpressure/capacity: {response.status_code}")
            if response.status_code == 401:
                return response.failure("Unauthorized - API key issue")
            if response.status_code == 404:
                return response.failure("Flow not found - check FLOW_ID")
            if response.status_code >= 500:
                return response.failure(f"Server error {response.status_code}")

            return response.failure(f"HTTP {response.status_code}")


class NormalUser(BaseLfxUser):
    """Normal user simulating typical API interactions.

    Based on the main stress test patterns with realistic message distribution.
    """

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


class AggressiveUser(BaseLfxUser):
    """Aggressive user with minimal wait times.

    Tests the system under extreme concurrent load.
    """

    weight = 3
    wait_time = between(0.1, 0.3)  # Very aggressive

    @task
    def rapid_fire(self):
        """Send requests as fast as possible."""
        self.make_request(message_type="simple", tag_suffix="-rapid")


class SustainedLoadUser(BaseLfxUser):
    """Maintains exactly 1 request/second for steady load testing.

    Based on constant throughput testing patterns.
    """

    weight = 3
    wait_time = constant_pacing(1)  # Exactly 1 request per second per user

    @task
    def steady_load(self):
        """Send requests at constant 1 RPS per user."""
        self.make_request(message_type="medium", tag_suffix="-steady")


class TailLatencyHunter(BaseLfxUser):
    """Mixed workload designed to expose tail latency issues.

    Alternates between light and heavy requests to stress the system.
    """

    weight = 3
    wait_time = between(0.8, 1.5)

    @task
    def hunt_tail_latency(self):
        """Alternate between simple and complex requests to find tail latency."""
        if random.random() < 0.7:  # noqa: S311
            self.make_request(message_type="simple", tag_suffix="-tail")
        else:
            self.make_request(message_type="large", tag_suffix="-tail-heavy")


class ScalabilityTestUser(BaseLfxUser):
    """Tests for the scalability cliff at 30 users.

    Uses patterns that specifically stress concurrency limits.
    """

    weight = 3
    wait_time = constant(1.0)  # Constant load to test scaling

    @task
    def scalability_test(self):
        """Send medium complexity requests to test scaling limits."""
        self.make_request(message_type="medium", tag_suffix="-scale")


class BurstUser(BaseLfxUser):
    """Sends bursts of 10 requests to test connection pooling.

    Based on connection pool exhaustion test patterns.
    """

    weight = 3
    wait_time = between(5, 10)  # Long wait between bursts

    @task
    def burst_attack(self):
        """Send a burst of 10 requests quickly to test connection handling."""
        for i in range(10):
            self.make_request(message_type="minimal", tag_suffix=f"-burst{i}")
            gevent.sleep(0.05)  # 50ms between requests in burst


# Auto-select shape based on environment variable

_shape_env = os.getenv("SHAPE", "").lower()
_selected = None

if _shape_env == "stepramp":
    _selected = StepRamp
elif _shape_env == "ramp100":
    _selected = RampToHundred

if _selected:
    # Create a single exported shape class and remove others so Locust sees only one
    class SelectedLoadTestShape(_selected):
        pass

    # Remove other shape classes so Locust auto-picks the selected one
    for _name, _obj in list(globals().items()):
        if (
            inspect.isclass(_obj)
            and issubclass(_obj, LoadTestShape)
            and _obj is not SelectedLoadTestShape
            and _obj is not LoadTestShape
        ):
            del globals()[_name]

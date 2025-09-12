"""Enhanced Langflow Locust Load Testing File
Based on the weakness-focused stress test scripts with additional user behaviors.

Usage:
    # Run with web UI (recommended)
    locust -f src/backend/tests/locust/locustfile_enhanced.py --host http://127.0.0.1:8000

    # Run headless
    locust -f src/backend/tests/locust/locustfile_enhanced.py --host http://127.0.0.1:8000 --headless -u 50 -r 5 -t 60s

    # Run distributed (master)
    locust -f src/backend/tests/locust/locustfile_enhanced.py --host http://127.0.0.1:8000 --master

    # Run distributed (worker)
    locust -f src/backend/tests/locust/locustfile_enhanced.py --host http://127.0.0.1:8000 --worker --master-host=localhost
"""

import json
import os
import random
import time

import gevent
from locust import FastHttpUser, between, constant, constant_pacing, events, task

# Configuration - can be overridden by environment variables
FLOW_ID = os.getenv("FLOW_ID", "5523731d-5ef3-56de-b4ef-59b0a224fdbc")
API_KEY = os.getenv("API_KEY", "test")
API_ENDPOINT = f"/flows/{FLOW_ID}/run"

# Test messages of varying complexity (from weakness_stress_test.py)
TEST_MESSAGES = {
    "minimal": "Hi",
    "simple": "Can you help me solve this problem?",
    "medium": "I need help understanding how machine learning algorithms work, particularly neural networks and deep learning. Can you explain the key concepts?",
    "large": "Please provide a comprehensive analysis of the following scenario: " + "x" * 500,
    "complex": "Analyze this data: " + json.dumps({f"field_{i}": f"value_{i}" * 10 for i in range(50)}),
}

# Message distribution (80% simple, 15% medium, 5% complex - from weakness test)
MESSAGE_WEIGHTS = [
    ("minimal", 40),
    ("simple", 40),
    ("medium", 15),
    ("large", 4),
    ("complex", 1),
]


class BaseLangflowUser(FastHttpUser):
    """Base class for all Langflow test users with common setup."""

    abstract = True  # This is a base class, not instantiated directly
    connection_timeout = 30.0
    network_timeout = 30.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = None
        self.request_count = 0
        self.slow_requests = 0
        self.start_time = time.time()

    def on_start(self):
        """Called when a user starts before any task is scheduled."""
        self.session_id = f"locust_{self.__class__.__name__}_{id(self)}_{int(time.time())}"

    def make_request(self, message_type="simple", tag_suffix=""):
        """Common request method used by all user types."""
        message = TEST_MESSAGES.get(message_type, TEST_MESSAGES["simple"])

        payload = {"input_value": message, "session_id": f"{self.session_id}_{self.request_count}"}

        headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}

        self.request_count += 1
        name = f"{API_ENDPOINT} [{message_type}{tag_suffix}]"

        # Track request timing manually
        start_time = time.time()

        with self.client.post(
            API_ENDPOINT,
            json=payload,
            headers=headers,
            catch_response=True,
            name=name,
            timeout=20,  # 20 second timeout like in weakness test
        ) as response:
            # Calculate response time manually
            response_time = time.time() - start_time

            # Track slow requests (>10s)
            if response_time > 10:
                self.slow_requests += 1

            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("success", False):
                        response.success()
                    else:
                        # Flow execution failed
                        error_msg = data.get("result", "Unknown error")
                        if len(error_msg) > 100:
                            error_msg = error_msg[:100] + "..."
                        response.failure(f"Flow failed: {error_msg}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 401:
                response.failure("Unauthorized - API key issue")
            elif response.status_code == 500:
                response.failure("Internal server error")
            else:
                response.failure(f"HTTP {response.status_code}")

    def on_stop(self):
        """Called when user stops."""
        time.time() - self.start_time
        if self.request_count > 0:
            pass


class NormalUser(BaseLangflowUser):
    """Normal user simulating typical API interactions.
    Based on the main stress test patterns.
    """

    wait_time = between(0.5, 2)  # Wait between requests

    @task(80)
    def send_message(self):
        """Main task: Send a message with weighted distribution."""
        message_type = random.choices([w[0] for w in MESSAGE_WEIGHTS], weights=[w[1] for w in MESSAGE_WEIGHTS], k=1)[0]

        self.make_request(message_type=message_type)

    @task(15)
    def send_burst(self):
        """Send a burst of 3 small messages quickly."""
        for i in range(3):
            self.make_request(message_type="minimal", tag_suffix=f"-burst{i}")
            if i < 2:
                gevent.sleep(0.1)

    @task(5)
    def send_complex(self):
        """Send a complex message."""
        self.make_request(message_type="complex")


class AggressiveUser(BaseLangflowUser):
    """Aggressive user that sends requests with minimal wait time.
    Simulates the "extreme concurrent" scenarios from stress tests.
    """

    wait_time = constant(0.1)  # Minimal wait - aggressive testing

    @task
    def rapid_fire(self):
        """Send messages as fast as possible."""
        # Use simple messages for speed
        self.make_request(message_type="simple", tag_suffix="-aggressive")


class SustainedLoadUser(BaseLangflowUser):
    """User that maintains consistent load over time.
    Simulates the "sustained high load" test from weakness testing.
    """

    wait_time = constant_pacing(1)  # Exactly 1 request per second per user

    @task
    def steady_load(self):
        """Maintain steady load with varied message types."""
        # Use only simple to medium messages for sustained load
        message_type = random.choice(["minimal", "simple", "medium"])
        self.make_request(message_type=message_type, tag_suffix="-sustained")


class TailLatencyHunter(BaseLangflowUser):
    """Special user designed to find tail latency issues.
    Sends mixed workload similar to the tail latency test.
    """

    wait_time = between(0.1, 5)  # Variable wait to create unpredictable load

    @task
    def hunt_tail_latency(self):
        """Send requests designed to expose tail latency."""
        # 80% simple, 15% medium, 5% complex (from weakness test)
        rand = random.random()
        if rand < 0.8:
            message_type = "simple"
        elif rand < 0.95:
            message_type = "medium"
        else:
            message_type = "complex"

        self.make_request(message_type=message_type, tag_suffix="-tail")


class ScalabilityTestUser(BaseLangflowUser):
    """User for testing scalability cliff.
    Similar to the scalability cliff detection from weakness test.
    """

    wait_time = between(1, 3)

    @task
    def scalability_test(self):
        """Send requests for scalability testing."""
        # Mix of message types
        message_type = random.choice(list(TEST_MESSAGES.keys()))
        self.make_request(message_type=message_type, tag_suffix="-scale")


class BurstUser(BaseLangflowUser):
    """User that sends bursts of requests to test connection pooling.
    Based on connection pool exhaustion test.
    """

    wait_time = between(5, 10)  # Long wait between bursts

    @task
    def burst_attack(self):
        """Send a burst of 10 requests quickly."""
        for i in range(10):
            self.make_request(message_type="minimal", tag_suffix=f"-burst{i}")
            gevent.sleep(0.05)  # 50ms between requests in burst


# Event handlers for additional metrics and reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    # Initialize custom metrics tracking
    environment.slow_request_count = 0
    environment.very_slow_request_count = 0


@events.request.add_listener
def track_slow_requests(request_type, name, response_time, response_length, exception, **kwargs):
    """Track requests that exceed certain thresholds."""
    # Convert to seconds for easier reading
    response_time_sec = response_time / 1000

    if response_time_sec > 10:
        if hasattr(kwargs.get("context", {}), "environment"):
            kwargs["context"].environment.slow_request_count += 1

        if response_time_sec > 20:
            if hasattr(kwargs.get("context", {}), "environment"):
                kwargs["context"].environment.very_slow_request_count += 1
        else:
            pass


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops."""
    # Print performance summary
    if environment.stats.total.num_requests > 0:
        # Calculate percentiles
        p95 = environment.stats.total.get_response_time_percentile(0.95) or 0
        environment.stats.total.get_response_time_percentile(0.99) or 0

        # Performance grade based on weakness test criteria
        grade = "A"
        issues = []

        if environment.stats.total.fail_ratio > 0.01:
            grade = "B"
            issues.append(f"Failure rate: {environment.stats.total.fail_ratio:.1%}")

        if environment.stats.total.fail_ratio > 0.05:
            grade = "C"

        if p95 > 10000:  # 10 seconds
            grade = "D" if grade > "C" else grade
            issues.append(f"P95 > 10s: {p95 / 1000:.1f}s")

        if p95 > 20000:  # 20 seconds
            grade = "F"
            issues.append(f"P95 > 20s: {p95 / 1000:.1f}s")

        # Warnings based on specific thresholds
        if environment.runner.user_count > 30:
            pass

        if p95 > 14000:
            pass

        if hasattr(environment, "slow_request_count") and environment.slow_request_count > 0:
            if hasattr(environment, "very_slow_request_count"):
                pass


# Helper function for running specific test scenarios
def run_scalability_cliff_test(host="http://127.0.0.1:8000", step_duration=30):
    """Programmatically run a scalability cliff detection test.
    Similar to the weakness test's scalability cliff detection.
    """
    from locust.env import Environment

    # Use mix of user types for realistic load
    env = Environment(user_classes=[NormalUser, AggressiveUser, ScalabilityTestUser], host=host)

    runner = env.create_local_runner()

    # Progressive load increase to find cliff
    user_counts = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]

    for user_count in user_counts:
        runner.start(user_count, spawn_rate=5)
        gevent.sleep(step_duration)

        # Get current stats
        stats = env.stats
        fail_ratio = stats.total.fail_ratio if stats.total.num_requests > 0 else 0
        avg_response = stats.total.avg_response_time if stats.total.num_requests > 0 else 0

        # Check for performance cliff (>5% failure or response time doubled)
        if fail_ratio > 0.05 or (user_count > 5 and avg_response > 10000):
            break

    runner.quit()
    return env.stats


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "cliff":
        run_scalability_cliff_test()
    else:
        pass

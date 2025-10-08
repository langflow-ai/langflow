"""LFX Step Ramp Load Test for Finding Performance Cliffs.

This file tests the LFX API (complex serve), not the Langflow API.

Steps every 30 seconds: 5 -> 10 -> 15 -> 20 -> 25 -> 30 -> 35 users.
Each step holds for exactly 30 seconds to measure steady-state performance.
"""

import json
import os
import time

from locust import FastHttpUser, LoadTestShape, between, events, task

# Configuration
FLOW_ID = os.getenv("FLOW_ID", "5523731d-5ef3-56de-b4ef-59b0a224fdbc")
API_KEY = os.getenv("API_KEY", "test")
API_ENDPOINT = f"/flows/{FLOW_ID}/run"

# Test messages
TEST_MESSAGES = {
    "minimal": "Hi",
    "simple": "Can you help me?",
    "medium": "I need help understanding how machine learning works in this context.",
    "complex": "Please analyze this data: " + "x" * 500 + " and provide detailed insights.",
    "large": "Here's a complex scenario: " + "data " * 1000,
}

MESSAGE_WEIGHTS = [("simple", 50), ("medium", 30), ("minimal", 15), ("complex", 4), ("large", 1)]


class StepRamp(LoadTestShape):
    """Step ramp for finding performance cliffs."""

    def tick(self):
        run_time = self.get_run_time()

        # Step every 30 seconds
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

        for time_limit, user_count in steps:
            if run_time < time_limit:
                return user_count, 10

        return None


# Event handlers for metrics
_env_bags = {}


@events.test_start.add_listener
def on_test_start(environment, **_kwargs):
    _env_bags[environment] = {"slow_10s": 0, "slow_20s": 0}


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
    stats = environment.stats.total
    if stats.num_requests == 0:
        return

    p95 = stats.get_response_time_percentile(0.95) or 0
    fail_ratio = stats.fail_ratio
    _env_bags.get(environment, {"slow_10s": 0, "slow_20s": 0})

    if fail_ratio > 0.05 or p95 > 10_000:
        pass
    else:
        pass

    _env_bags.pop(environment, None)


class BaseLangflowUser(FastHttpUser):
    abstract = True
    REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "10"))

    def on_start(self):
        self.session_id = f"step_{self.__class__.__name__}_{id(self)}_{int(time.time())}"
        self.request_count = 0

    def make_request(self, message_type="simple", tag_suffix=""):
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

            if response.status_code in (429, 503):
                return response.failure(f"Backpressure: {response.status_code}")
            if response.status_code == 401:
                return response.failure("Unauthorized")
            if response.status_code == 404:
                return response.failure("Not Found - possible bad FLOW_ID or misconfiguration")
            if response.status_code >= 500:
                return response.failure(f"Server error {response.status_code}")
            return response.failure(f"HTTP {response.status_code}")


class StepTestUser(BaseLangflowUser):
    """User class for step ramp testing - sends medium complexity requests."""

    wait_time = between(1, 2)

    @task
    def step_test(self):
        self.make_request(message_type="medium", tag_suffix="-step")

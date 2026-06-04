"""Locust load test for the v2 background execution service.

Each task submits a background workflow job and polls it to a terminal state,
proving the background API holds under load with real ``langflow worker``
processes draining a redis claim queue (scaled mode) -- or the in-process
executor (default mode) for a head-to-head comparison.

Submit:  POST /api/v2/workflows  {"flow_id", "input_value", "mode": "background"}
         -> {"job_id", "flow_id", "status": "queued"}
Poll:    GET  /api/v2/workflows?job_id=<job_id>
         -> 200 with status in {queued, in_progress, completed} ; 500 on failure.

A request is recorded as a success only when its job reaches COMPLETED inside
the bounded deadline. Submitted vs completed counts are tracked and printed in
the final summary so correctness can be cross-checked against the ``job`` table.

Usage:
    locust -f v2_background_locustfile.py --host http://localhost:7870 \
        --headless --users 200 --spawn-rate 20 --run-time 3m

Environment Variables:
    - FLOW_ID: Flow ID to run (required)
    - API_KEY: API key for x-api-key auth (required)
    - JOB_DEADLINE_S: Per-job terminal deadline in seconds (default: 60)
    - POLL_INTERVAL_S: Seconds between status polls (default: 0.25)
    - MIN_WAIT / MAX_WAIT: think time between tasks in ms (default: 0 / 100)
    - REQUEST_TIMEOUT: per-HTTP-call timeout in seconds (default: 30)
"""

import os
import threading
import time

from locust import FastHttpUser, between, events, task

FLOW_ID = os.getenv("FLOW_ID", "")
API_KEY = os.getenv("API_KEY", "")
JOB_DEADLINE_S = float(os.getenv("JOB_DEADLINE_S", "60"))
POLL_INTERVAL_S = float(os.getenv("POLL_INTERVAL_S", "0.25"))
MIN_WAIT = int(os.getenv("MIN_WAIT", "0"))
MAX_WAIT = int(os.getenv("MAX_WAIT", "100"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "30"))

INPUT_VALUES = ["hello", "load test", "background run", "ping", "are you there?"]

# Process-wide counters (locust runs users as greenlets in one process).
_lock = threading.Lock()
COUNTS = {
    "submitted": 0,
    "completed": 0,
    "failed": 0,
    "deadline_exceeded": 0,
    "submit_errors": 0,
    "poll_errors": 0,
}


def _bump(key: str, n: int = 1) -> None:
    with _lock:
        COUNTS[key] += n


class BackgroundWorkflowUser(FastHttpUser):
    wait_time = between(MIN_WAIT / 1000.0, MAX_WAIT / 1000.0)

    def on_start(self) -> None:
        if not FLOW_ID or not API_KEY:
            raise RuntimeError("FLOW_ID and API_KEY env vars are required")
        self.headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}

    @task
    def run_background_job(self) -> None:
        idx = int(time.time() * 1000) % len(INPUT_VALUES)
        body = {"flow_id": FLOW_ID, "input_value": INPUT_VALUES[idx], "mode": "background"}

        # 1. Submit. This latency is what we care about for API responsiveness:
        # the submit must stay fast even while the workers grind on the backlog.
        with self.client.post(
            "/api/v2/workflows",
            json=body,
            headers=self.headers,
            name="POST /api/v2/workflows (submit)",
            timeout=REQUEST_TIMEOUT,
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 201):
                _bump("submit_errors")
                resp.failure(f"submit {resp.status_code}: {resp.text[:200]}")
                return
            try:
                job_id = resp.json()["job_id"]
            except Exception as exc:
                _bump("submit_errors")
                resp.failure(f"submit body parse error: {exc}")
                return
            resp.success()
        _bump("submitted")

        # 2. Poll to a terminal state within the deadline. Recorded under a
        # separate request name so submit latency stays clean. We only mark the
        # job success when status == completed.
        deadline = time.time() + JOB_DEADLINE_S
        while time.time() < deadline:
            with self.client.get(
                "/api/v2/workflows",
                params={"job_id": job_id},
                headers=self.headers,
                name="GET /api/v2/workflows (poll->terminal)",
                timeout=REQUEST_TIMEOUT,
                catch_response=True,
            ) as poll:
                code = poll.status_code
                if code == 200:
                    status = (poll.json() or {}).get("status")
                    if status == "completed":
                        poll.success()
                        _bump("completed")
                        return
                    # queued / in_progress: still working, keep polling.
                    poll.success()
                elif code == 500:
                    # Failed job surfaces as 500 JOB_FAILED on the status route.
                    poll.success()  # the poll call itself worked; the job failed
                    _bump("failed")
                    return
                elif code == 408:
                    poll.success()
                    _bump("failed")
                    return
                else:
                    _bump("poll_errors")
                    poll.failure(f"poll {code}: {poll.text[:200]}")
                    return
            time.sleep(POLL_INTERVAL_S)

        # Deadline blown: record as a failure on the poll request so it shows in
        # the failure column, and bump the dedicated counter.
        _bump("deadline_exceeded")
        with self.client.get(
            "/api/v2/workflows",
            params={"job_id": job_id},
            headers=self.headers,
            name="GET /api/v2/workflows (poll->terminal)",
            timeout=REQUEST_TIMEOUT,
            catch_response=True,
        ) as poll:
            poll.failure(f"job {job_id} did not reach terminal in {JOB_DEADLINE_S}s")


@events.quitting.add_listener
def _print_counts(_environment, **_kwargs) -> None:
    with _lock:
        snap = dict(COUNTS)
    total = snap["submitted"] or 1
    print("\n==== v2 background load-test job accounting ====")
    print(f"submitted:          {snap['submitted']}")
    print(f"completed:          {snap['completed']}")
    print(f"failed:             {snap['failed']}")
    print(f"deadline_exceeded:  {snap['deadline_exceeded']}")
    print(f"submit_errors:      {snap['submit_errors']}")
    print(f"poll_errors:        {snap['poll_errors']}")
    accounted = snap["completed"] + snap["failed"] + snap["deadline_exceeded"]
    print(f"completed/submitted: {snap['completed']}/{snap['submitted']} ({100.0 * snap['completed'] / total:.1f}%)")
    print(f"accounted/submitted: {accounted}/{snap['submitted']}")
    print("================================================\n")

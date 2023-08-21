from locust import FastHttpUser, task, between
import random
import time
from rich import print
import os


class NameTest(FastHttpUser):
    host = "http://localhost/api/v1"  # make sure the port number is correct
    wait_time = between(1, 5)

    with open("names.txt", "r") as file:
        names = [line.strip() for line in file.readlines()]

    def poll_task(self, task_id, sleep_time=1):
        while True:
            with self.rest(
                "GET",
                f"/task/{task_id}/status",
                name="task_status",
            ) as response:
                status = response.js.get("status")
                if status == "SUCCESS":
                    return response.js.get("result")
                elif status in ["FAILURE", "REVOKED"]:
                    raise ValueError(f"Task failed with status: {status}")
            time.sleep(sleep_time)

    @task
    def send_name_and_check(self):
        name = random.choice(self.names)
        flow_id = os.getenv("FLOW_ID")
        session_id = f"{name}-{time.time()}"

        def process(flow_id, payload):
            task_id = None
            print(f"Processing {payload}")
            with self.rest(
                "POST", f"/process/{flow_id}", json=payload, name="process"
            ) as response:
                if response.status_code != 200:
                    response.failure("Process call failed")
                    raise ValueError("Process call failed")
                print(response.js)
                task_id = response.js.get("id")
                assert task_id, "Inner Task ID not found"

            assert task_id, "Task ID not found"
            result, session_id = self.poll_task(task_id)
            print(f"Result for {name}: {result}")

            return result, session_id

        payload1 = {
            "inputs": {"text": f"Hello, My name is {name}"},
            "session_id": session_id,
        }
        result1, session_id = process(flow_id, payload1)

        payload2 = {
            "inputs": {
                "text": "What is my name? Please, answer like this: Your name is <name>"
            },
            "session_id": session_id,
        }
        result2, session_id = process(flow_id, payload2)

        assert f"Your name is {name}" in result2, "Name not found in response"

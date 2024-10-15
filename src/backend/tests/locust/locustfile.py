import random
import time
from pathlib import Path

import httpx
import orjson
from locust import FastHttpUser, between, task
from rich import print


class NameTest(FastHttpUser):
    wait_time = between(1, 5)

    with Path("names.txt").open() as file:
        names = [line.strip() for line in file.readlines()]

    headers: dict = {}

    def poll_task(self, task_id, sleep_time=1):
        while True:
            with self.rest(
                "GET",
                f"/task/{task_id}",
                name="task_status",
                headers=self.headers,
            ) as response:
                status = response.js.get("status")
                print(f"Poll Response: {response.js}")
                if status == "SUCCESS":
                    return response.js.get("result")
                elif status in ["FAILURE", "REVOKED"]:
                    raise ValueError(f"Task failed with status: {status}")
            time.sleep(sleep_time)

    def process(self, name, flow_id, payload):
        task_id = None
        print(f"Processing {payload}")
        with self.rest(
            "POST",
            f"/process/{flow_id}",
            json=payload,
            name="process",
            headers=self.headers,
        ) as response:
            print(response.js)
            if response.status_code != 200:
                response.failure("Process call failed")
                raise ValueError("Process call failed")
            task_id = response.js.get("id")
            session_id = response.js.get("session_id")
            assert task_id, "Inner Task ID not found"

        assert task_id, "Task ID not found"
        result = self.poll_task(task_id)
        print(f"Result for {name}: {result}")

        return result, session_id

    @task
    def send_name_and_check(self):
        name = random.choice(self.names)

        payload1 = {
            "inputs": {"text": f"Hello, My name is {name}"},
            "sync": False,
        }
        _result1, session_id = self.process(name, self.flow_id, payload1)

        payload2 = {
            "inputs": {"text": "What is my name? Please, answer like this: Your name is <name>"},
            "session_id": session_id,
            "sync": False,
        }
        result2, session_id = self.process(name, self.flow_id, payload2)

        assert f"Your name is {name}" in str(result2), "Name not found in response"

    def on_start(self):
        print("Starting")
        login_data = {"username": "superuser", "password": "superuser"}
        response = httpx.post(f"{self.host}/login", data=login_data)
        print(response.json())

        tokens = response.json()
        print(tokens)
        a_token = tokens["access_token"]
        logged_in_headers = {"Authorization": f"Bearer {a_token}"}
        print("Logged in")
        json_flow = (Path(__file__).parent.parent / "data" / "BasicChatwithPromptandHistory.json").read_text()
        flow = orjson.loads(json_flow)
        data = flow["data"]
        # Create test data
        flow = {"name": "Flow 1", "description": "description", "data": data}
        print("Creating flow")
        # Make request to endpoint
        response = httpx.post(
            f"{self.host}/flows/",
            json=flow,
            headers=logged_in_headers,
        )
        self.flow_id = response.json()["id"]
        print(f"Flow ID: {self.flow_id}")

        # read all users
        response = httpx.get(
            f"{self.host}/users/",
            headers=logged_in_headers,
        )
        print(response.json())
        user_id = next(
            (user["id"] for user in response.json()["users"] if user["username"] == "superuser"),
            None,
        )
        # Create api key
        response = httpx.post(
            f"{self.host}/api_key/",
            json={"user_id": user_id},
            headers=logged_in_headers,
        )
        print(response.json())
        self.headers["x-api-key"] = response.json()["api_key"]

from locust import HttpUser, task, between
import random


class NameTest(HttpUser):
    host = "http://localhost:/api/v1"
    wait_time = between(1, 5)

    # Read names from the file
    with open("names.txt", "r") as file:
        names = [line.strip() for line in file.readlines()]

    @task
    def send_name_and_check(self):
        # Select a random name or in order from the list
        name = random.choice(self.names)
        flow_id = "0bc439e4-539c-4b18-9813-92729326b171"  # Replace with the appropriate flow ID
        random_session_id_with_name = f"{name}-{random.randint(0, 1000000)}"
        session_id = None
        # First input
        payload1 = {
            "inputs": {"text": f"Hello, My name is {name}"},
            "session_id": random_session_id_with_name,
        }
        with self.client.post(
            f"/process/{flow_id}", json=payload1, catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Error: {response.json()}")
            else:
                response.success()

                session_id = response.json().get("session_id")
                print(f"Session ID: {session_id}")

        if not session_id:
            raise ValueError("Session ID not found")

        # Second input
        payload2 = {"inputs": {"text": "What is my name?"}, "session_id": session_id}
        with self.client.post(
            f"/process/{flow_id}", json=payload2, catch_response=True
        ) as response2:
            if name not in response2.text:
                response2.failure(f"Error {name} not in response: {response2.json()}")
            else:
                response2.success()

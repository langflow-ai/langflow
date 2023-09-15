import time


def run_post(client, flow_id, headers, post_data):
    response = client.post(
        f"api/v1/process/{flow_id}",
        headers=headers,
        json=post_data,
    )
    assert response.status_code == 200, response.json()
    return response.json()


# Helper function to poll task status
def poll_task_status(client, headers, task_id, max_attempts=20, sleep_time=1):
    for _ in range(max_attempts):
        task_status_response = client.get(
            f"api/v1/task/{task_id}/status",
            headers=headers,
        )
        if (
            task_status_response.status_code == 200
            and task_status_response.json()["status"] == "SUCCESS"
        ):
            return task_status_response.json()
        time.sleep(sleep_time)
    return None  # Return None if task did not complete in time

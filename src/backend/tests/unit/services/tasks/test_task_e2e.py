import asyncio
import os
import time
from uuid import uuid4

import pytest
from fastapi.encoders import jsonable_encoder
from langflow.components.agents.agent import AgentComponent
from langflow.components.inputs.chat import ChatInput
from langflow.components.outputs.chat import ChatOutput
from langflow.components.tasks.flows_lister import FlowsListerComponent
from langflow.components.tasks.task_creator import TaskCreatorComponent
from langflow.graph import Graph
from langflow.initial_setup.starter_projects.basic_prompting import basic_prompting_graph
from langflow.services.database.models.flow.model import FlowCreate
from langflow.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI
from loguru import logger


@pytest.fixture
async def tasks_agent_graph():
    session_id = str(uuid4())
    agent = AgentComponent(
        _type="Agent",
        add_current_date_tool=True,
        agent_llm="OpenAI",
        model_name="gpt-4o-mini",
        handle_parsing_errors=True,
        api_key=os.getenv("OPENAI_API_KEY"),
        max_iterations=10,
        verbose=True,
        sender=MESSAGE_SENDER_AI,
        sender_name=MESSAGE_SENDER_NAME_AI,
        system_prompt="""You are a task management assistant.
        When asked to create a task, you MUST use the task creation
        tool. The assignee should be the flow you want to run. You will be the author of the task.
        Always use the tool exactly as instructed. The input will include task title and description
        which you should use when creating new tasks. Be thorough and ensure all task details
        are properly captured.
        Use the flows lister, get the id of the flow you want to use and use it to create the task.
        If something goes wrong, just say you couldn't <the task description> because <reason>. """,
    )
    task_creator = TaskCreatorComponent()
    flows_lister = FlowsListerComponent()
    agent.set(tools=[task_creator.to_toolkit, flows_lister.to_toolkit])
    chat_input = ChatInput()
    chat_output = ChatOutput()
    agent.set(input_value=chat_input)
    chat_output.set(input_value=agent)
    graph = Graph(start=chat_input, end=chat_output)
    graph.session_id = session_id
    return graph


@pytest.fixture
async def agent_flow(tasks_agent_graph: Graph, client, logged_in_headers):
    graph_dict = tasks_agent_graph.dump(name="Tasks Agent")

    # Convert the graph_dict to a regular dict to ensure proper serialization
    flow = FlowCreate(**graph_dict)
    # Use model_dump() to get a serializable dictionary
    response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    yield response.json()
    await client.delete(f"api/v1/flows/{response.json()['id']}", headers=logged_in_headers)


@pytest.fixture
async def reporter_flow(client, logged_in_headers):
    # Create a basic prompting graph with a template for report building
    template = """You are a report building assistant. Create a detailed report on the topic provided.

User: {user_input}

Report:
"""
    graph = basic_prompting_graph(template=template)
    graph_dict = graph.dump(name="Report Builder", description="This flow builds a report on the topic provided.")

    # Convert the graph_dict to a regular dict to ensure proper serialization
    flow = FlowCreate(**graph_dict)
    # Use model_dump() to get a serializable dictionary
    response = await client.post("api/v1/flows/", json=jsonable_encoder(flow), headers=logged_in_headers)
    assert response.status_code == 201

    yield response.json()
    await client.delete(f"api/v1/flows/{response.json()['id']}", headers=logged_in_headers)


@pytest.mark.asyncio
async def test_agent_task_update(client, logged_in_headers, agent_flow, reporter_flow, active_user):
    """Test the agent that can update tasks."""
    # Get the session_id from the task_agent_graph or create a new one
    session_id = str(uuid4())  # Always create a fresh session ID

    # Verify both flows exist before starting the test
    flows_response = await client.get("api/v1/flows/", headers=logged_in_headers)
    assert flows_response.status_code == 200
    flows = flows_response.json()
    flow_ids = [flow["id"] for flow in flows]
    user_ids = [flow["user_id"] for flow in flows]
    assert agent_flow["id"] in flow_ids
    assert reporter_flow["id"] in flow_ids
    assert str(active_user.id) in user_ids

    # Create a task with unique title and description that can be easily verified
    unique_id = str(uuid4())[:8]  # Use first 8 chars of UUID for readability
    task_title = f"Test task {unique_id}"
    task_description = (
        f"This is a test task with unique ID: {unique_id}. You need to create a task assigned "
        f"specifically to the Report Builder flow with ID '{reporter_flow['id']}'. The task should "
        f"make the Report Builder generate a comprehensive report about elephants including detailed "
        f"information about their habitat, behavior, and conservation status. The report must "
        f"explicitly mention the word 'elephant' multiple times."
    )
    task_data = {
        "title": task_title,
        "description": task_description,
        "attachments": [],
        "author_id": str(active_user.id),
        "assignee_id": agent_flow["id"],
        "category": "agent",
        "state": "initial",
        "status": "pending",
    }

    # Create the task
    response = await client.post("api/v1/tasks/", json=task_data, headers=logged_in_headers)
    assert response.status_code == 201
    task_id = response.json()["id"]

    # Step 2: Update the task with the input message that would trigger the agent

    # First check if we can retrieve the flow data
    task_check = await client.get(f"api/v1/tasks/{task_id}", headers=logged_in_headers)
    assert task_check.status_code == 200
    task_before_update = task_check.json()

    # Assert task was created with the correct properties
    assert task_before_update["title"] == task_title
    assert task_before_update["description"] == task_description
    assert task_before_update["status"] == "pending"

    # Use the same flow_data from the task creation, ensuring session_id is set at all levels
    update_data = {
        "status": "processing",  # Set to processing to trigger processing
        "input_request": {
            "session_id": session_id,  # Include the session_id in the input_request
            "sender": MESSAGE_SENDER_AI,  # Include the sender
            "sender_name": MESSAGE_SENDER_NAME_AI,  # Include the sender_name
        },
    }

    # Update the task
    update_response = await client.put(f"api/v1/tasks/{task_id}", json=update_data, headers=logged_in_headers)
    assert update_response.status_code == 200

    # Wait for the task to be processed (poll for status)
    max_retries = 30  # Increase retries to give more time for completion
    retry_count = 0
    task_completed = False
    task_processed = None

    while retry_count < max_retries and not task_completed:
        task_response = await client.get(f"api/v1/tasks/{task_id}", headers=logged_in_headers)
        assert task_response.status_code == 200
        task_processed = task_response.json()
        if task_processed["status"] in ["completed", "failed"]:
            task_completed = True
        else:
            retry_count += 1
            await asyncio.sleep(1)

    # The agent task should be completed
    assert task_processed["status"] == "completed", f"Task failed: {task_processed.get('result', {})}"

    # Verify that the task has a result
    assert task_processed["result"] is not None, "Task should have a result after processing"
    assert task_processed["result"], "Task result should not be empty"

    # Verify the value of the first output message text
    assert "outputs" in task_processed["result"], "Task result should contain outputs"
    assert len(task_processed["result"]["outputs"]) > 0, "Task result should have at least one output"
    assert "value" in task_processed["result"]["outputs"][0], "First output should have a value"
    assert "message" in task_processed["result"]["outputs"][0]["value"], "Value should contain a message"
    assert "text" in task_processed["result"]["outputs"][0]["value"]["message"], "Message should contain text"
    message_text = task_processed["result"]["outputs"][0]["value"]["message"]["text"]
    assert message_text, "Message text should not be empty"

    # Step 5: Check if a new task was created for the Report Builder
    # Get all tasks that were created recently
    tasks_response = await client.get("api/v1/tasks/", headers=logged_in_headers)
    assert tasks_response.status_code == 200
    all_tasks = tasks_response.json()

    # Look for a task assigned to the Report Builder flow
    report_builder_tasks = [
        task
        for task in all_tasks
        if task.get("assignee_id") == reporter_flow["id"] and task["created_at"] > task_processed.get("created_at")
    ]
    all_tasks_assignee_ids = [task["assignee_id"] for task in all_tasks]

    # Debug: Print all tasks and their descriptions

    # Assert that at least one task was specifically assigned to the Report Builder
    assert len(report_builder_tasks) > 0, (
        f"No tasks were assigned to the Report Builder flow (ID: {reporter_flow['id']}). "
        f"Assignee IDs found: {all_tasks_assignee_ids}"
    )

    # Use the first Report Builder task for testing
    report_task = report_builder_tasks[0]
    report_task_id = report_task["id"]

    # Assert the Report Builder task has appropriate description containing the word "elephant"
    assert (
        "elephant" in report_task["description"].lower()
    ), f"Report task description should mention elephants. Description: {report_task['description']}"

    # Assert initial task state
    assert report_task["status"] in [
        "pending",
        "processing",
    ], f"Report task status should be pending or processing, got {report_task['status']}"

    # IMPORTANT: Explicitly trigger the task processing
    report_start_data = {"status": "processing", "state": "processing"}
    report_update_response = await client.put(
        f"api/v1/tasks/{report_task_id}", json=report_start_data, headers=logged_in_headers
    )
    assert report_update_response.status_code == 200, f"Failed to update report task: {report_update_response.text}"

    # Step 6: Check if the task was executed (or at least started processing)
    # Wait for the task to be processed (poll for status with timeout)
    max_retries = 30  # Increase retries to allow time for completion
    retry_count = 0
    report_task_started = False
    report_task_completed = False
    report_task_current = None

    while retry_count < max_retries and not report_task_completed:
        report_task_response = await client.get(f"api/v1/tasks/{report_task_id}", headers=logged_in_headers)
        assert report_task_response.status_code == 200
        report_task_current = report_task_response.json()

        # Check if the task is processing (for debugging)
        if not report_task_started and report_task_current["status"] in ["processing"]:
            report_task_started = True

        # Check if the task is completed
        if report_task_current["status"] == "completed":
            report_task_completed = True
        else:
            retry_count += 1
            await asyncio.sleep(1)

    # First assert that the Report Builder task started (less strict check)
    assert report_task_started, "Report Builder task was not even started for processing"

    # Then check if it completed (with helpful debug info if it didn't)
    if report_task_completed:
        # Verify the report task result contains something about elephants if it completed
        assert report_task_current.get("result") is not None, "Completed report task should have a result"
        if (
            report_task_current.get("result")
            and isinstance(report_task_current["result"], dict)
            and "outputs" in report_task_current["result"]
        ):
            # Check if any output contains text about elephants
            output_texts = []
            for output in report_task_current["result"]["outputs"]:
                if "value" in output and "message" in output["value"] and "text" in output["value"]["message"]:
                    text = output["value"]["message"]["text"].lower()
                    output_texts.append(text)

            # At least one output should exist
            assert len(output_texts) > 0, "Report task should have at least one output text"

            # Make this a strict requirement instead of just a warning
            # Check for any elephant or Elephant content (case insensitive)
            elephant_related = False
            for text in output_texts:
                if "elephant" in text.lower():
                    elephant_related = True
                    break

            # Use a more informative assertion message with report content preview if available
            if not elephant_related and output_texts:
                preview = output_texts[0][:200] + "..." if len(output_texts[0]) > 200 else output_texts[0]
                assert elephant_related, (
                    f"Report should contain content about elephants, but none was found.\n"
                    f"Report content preview: {preview}"
                )
            else:
                assert elephant_related, "Report should contain content about elephants, but none was found"

    # Clean up - delete the report task if it exists
    try:
        delete_response = await client.delete(f"api/v1/tasks/{report_task_id}", headers=logged_in_headers)
        assert delete_response.status_code == 200, f"Failed to delete report task: {delete_response.text}"
    except (ValueError, KeyError, AssertionError) as e:
        # This is cleanup code, we don't want test to fail if cleanup fails
        # But we should log the error
        logger.error(f"Failed to delete report task: {e}")


@pytest.mark.asyncio
async def test_task_processing_service(agent_flow, client, logged_in_headers):
    """Test that the task processing service properly processes a task from creation to completion."""
    # Step 1: Create a test task
    flow_id = agent_flow["id"]
    unique_test_data = f"test_data_{uuid4()}"

    task_data = {
        "title": "Processing Test Task",
        "description": f"This task needs to be processed with {unique_test_data}",
        "attachments": [],
        "author_id": flow_id,
        "assignee_id": flow_id,
        "category": "processing_test",
        "state": "ready_for_processing",
        "status": "pending",
        "input_request": {"message": f"Process this task with data: {unique_test_data}"},
        "flow_data": agent_flow,
    }

    # Create the task using the API
    response = await client.post("api/v1/tasks/", json=task_data, headers=logged_in_headers)
    assert response.status_code == 201
    task = response.json()
    task_id = task["id"]

    # Step 2: Start processing the task immediately via task_orchestration_service
    start_task_data = {"status": "processing", "state": "processing"}

    # Update task status to trigger processing
    response = await client.put(f"api/v1/tasks/{task_id}", json=start_task_data, headers=logged_in_headers)
    assert response.status_code == 200

    # Step 3: Poll the task until it's completed or timeout after 45 seconds
    start_time = time.time()
    timeout = 45  # Increase timeout for processing
    task_processed = False

    while time.time() - start_time < timeout:
        # Check the task status
        response = await client.get(f"api/v1/tasks/{task_id}", headers=logged_in_headers)
        assert response.status_code == 200
        updated_task = response.json()

        # If the task has been completed or failed, we're done
        if updated_task["status"] in ["completed", "failed"]:
            task_processed = True
            break

        # Wait before polling again
        await asyncio.sleep(2)

    # Step 4: Verify the task was processed
    assert task_processed, f"Task was not processed within {timeout} seconds"

    # Get the final task state
    response = await client.get(f"api/v1/tasks/{task_id}", headers=logged_in_headers)
    final_task = response.json()

    # Check that the task has a result
    assert final_task["result"] is not None, "Task should have a result after processing"

    # Clean up - delete the task
    response = await client.delete(f"api/v1/tasks/{task_id}", headers=logged_in_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_consumer_worker_event_handling(agent_flow, client, logged_in_headers):
    """Test that the consumer worker properly handles task events."""
    # Step 1: Create a test task with unique identifier
    flow_id = agent_flow["id"]
    unique_id = str(uuid4())
    unique_result = {"test_result": f"result_{unique_id}"}

    task_data = {
        "title": f"Consumer Test Task {unique_id}",
        "description": "This task is for testing consumer event handling",
        "attachments": [],
        "author_id": flow_id,
        "assignee_id": flow_id,
        "category": "consumer_test",
        "state": "consumer_test",
        "status": "pending",
        "input_request": {"message": "Test consumer worker"},
        "flow_data": agent_flow,
    }

    # Create the task using the API
    response = await client.post("api/v1/tasks/", json=task_data, headers=logged_in_headers)
    assert response.status_code == 201
    task = response.json()
    task_id = task["id"]

    # Step 2: Update the task with a result, which should trigger events
    update_data = {
        "status": "completed",
        "state": "success",
        "result": unique_result,
        # Add flow_id to ensure proper routing of events
        "flow_id": flow_id,
    }
    response = await client.put(f"api/v1/tasks/{task_id}", json=update_data, headers=logged_in_headers)
    assert response.status_code == 200

    # Step 3: Wait a short time for the consumer to process the events
    await asyncio.sleep(3)  # Increase sleep time to ensure events are processed

    # Step 4: Verify the task state was properly updated by the consumer
    response = await client.get(f"api/v1/tasks/{task_id}", headers=logged_in_headers)
    assert response.status_code == 200
    updated_task = response.json()

    # Check that task status is completed
    assert updated_task["status"] == "completed", "Task status should be completed"

    # Check that the result contains our unique identifier
    assert updated_task["result"] is not None, "Task result should not be None"
    assert (
        "test_result" in updated_task["result"]
    ), f"Task result should contain test_result key, got: {updated_task['result']}"
    assert (
        updated_task["result"]["test_result"] == f"result_{unique_id}"
    ), "Task result should contain our unique identifier"

    # Clean up - delete the task
    response = await client.delete(f"api/v1/tasks/{task_id}", headers=logged_in_headers)
    assert response.status_code == 200

    assert response.status_code == 200

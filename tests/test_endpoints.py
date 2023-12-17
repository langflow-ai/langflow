import time
import uuid
from collections import namedtuple

import pytest
from fastapi.testclient import TestClient
from langflow.interface.tools.constants import CUSTOM_TOOLS
from langflow.processing.process import Result
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_db_service, get_settings_service
from langflow.template.frontend_node.chains import TimeTravelGuideChainNode


def run_post(client, flow_id, headers, post_data):
    response = client.post(
        f"api/v1/process/{flow_id}",
        headers=headers,
        json=post_data,
    )
    assert response.status_code == 200, response.json()
    return response.json()


# Helper function to poll task status
def poll_task_status(client, headers, href, max_attempts=20, sleep_time=2):
    for _ in range(max_attempts):
        task_status_response = client.get(
            href,
            headers=headers,
        )
        if task_status_response.status_code == 200 and task_status_response.json()["status"] == "SUCCESS":
            return task_status_response.json()
        time.sleep(sleep_time)
    return None  # Return None if task did not complete in time


PROMPT_REQUEST = {
    "name": "string",
    "template": "string",
    "frontend_node": {
        "template": {},
        "description": "string",
        "base_classes": ["string"],
        "name": "",
        "display_name": "",
        "documentation": "",
        "custom_fields": {},
        "output_types": [],
        "field_formatters": {
            "formatters": {"openai_api_key": {}},
            "base_formatters": {
                "kwargs": {},
                "optional": {},
                "list": {},
                "dict": {},
                "union": {},
                "multiline": {},
                "show": {},
                "password": {},
                "default": {},
                "headers": {},
                "dict_code_file": {},
                "model_fields": {
                    "MODEL_DICT": {
                        "OpenAI": [
                            "text-davinci-003",
                            "text-davinci-002",
                            "text-curie-001",
                            "text-babbage-001",
                            "text-ada-001",
                        ],
                        "ChatOpenAI": [
                            "gpt-3.5-turbo-0613",
                            "gpt-3.5-turbo",
                            "gpt-3.5-turbo-16k-0613",
                            "gpt-3.5-turbo-16k",
                            "gpt-4-0613",
                            "gpt-4-32k-0613",
                            "gpt-4",
                            "gpt-4-32k",
                        ],
                        "Anthropic": [
                            "claude-v1",
                            "claude-v1-100k",
                            "claude-instant-v1",
                            "claude-instant-v1-100k",
                            "claude-v1.3",
                            "claude-v1.3-100k",
                            "claude-v1.2",
                            "claude-v1.0",
                            "claude-instant-v1.1",
                            "claude-instant-v1.1-100k",
                            "claude-instant-v1.0",
                        ],
                        "ChatAnthropic": [
                            "claude-v1",
                            "claude-v1-100k",
                            "claude-instant-v1",
                            "claude-instant-v1-100k",
                            "claude-v1.3",
                            "claude-v1.3-100k",
                            "claude-v1.2",
                            "claude-v1.0",
                            "claude-instant-v1.1",
                            "claude-instant-v1.1-100k",
                            "claude-instant-v1.0",
                        ],
                    }
                },
            },
        },
    },
}


@pytest.fixture
def created_api_key(active_user):
    hashed = get_password_hash("random_key")
    api_key = ApiKey(
        name="test_api_key",
        user_id=active_user.id,
        api_key="random_key",
        hashed_api_key=hashed,
    )
    db_manager = get_db_service()
    with session_getter(db_manager) as session:
        if existing_api_key := session.query(ApiKey).filter(ApiKey.api_key == api_key.api_key).first():
            return existing_api_key
        session.add(api_key)
        session.commit()
        session.refresh(api_key)
    return api_key


def test_process_flow_invalid_api_key(client, flow, monkeypatch):
    # Mock de process_graph_cached
    from langflow.api.v1 import endpoints
    from langflow.services.database.models.api_key import crud

    settings_service = get_settings_service()
    settings_service.auth_settings.AUTO_LOGIN = False

    async def mock_process_graph_cached(*args, **kwargs):
        return Result(result={}, session_id="session_id_mock")

    def mock_update_total_uses(*args, **kwargs):
        return created_api_key

    monkeypatch.setattr(endpoints, "process_graph_cached", mock_process_graph_cached)
    monkeypatch.setattr(crud, "update_total_uses", mock_update_total_uses)

    headers = {"x-api-key": "invalid_api_key"}

    post_data = {
        "inputs": {"key": "value"},
        "tweaks": None,
        "clear_cache": False,
        "session_id": None,
    }

    response = client.post(f"api/v1/process/{flow.id}", headers=headers, json=post_data)

    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid or missing API key"}


def test_process_flow_invalid_id(client, monkeypatch, created_api_key):
    async def mock_process_graph_cached(*args, **kwargs):
        return Result(result={}, session_id="session_id_mock")

    from langflow.api.v1 import endpoints

    monkeypatch.setattr(endpoints, "process_graph_cached", mock_process_graph_cached)

    api_key = created_api_key.api_key
    headers = {"x-api-key": api_key}

    post_data = {
        "inputs": {"key": "value"},
        "tweaks": None,
        "clear_cache": False,
        "session_id": None,
    }

    invalid_id = uuid.uuid4()
    response = client.post(f"api/v1/process/{invalid_id}", headers=headers, json=post_data)

    assert response.status_code == 404
    assert f"Flow {invalid_id} not found" in response.json()["detail"]


def test_process_flow_without_autologin(client, flow, monkeypatch, created_api_key):
    # Mock de process_graph_cached
    from langflow.api.v1 import endpoints
    from langflow.services.database.models.api_key import crud

    settings_service = get_settings_service()
    settings_service.auth_settings.AUTO_LOGIN = False

    async def mock_process_graph_cached(*args, **kwargs):
        return Result(result={}, session_id="session_id_mock")

    def mock_process_graph_cached_task(*args, **kwargs):
        return Result(result={}, session_id="session_id_mock")

    # The task function is ran like this:
    # if not self.use_celery:
    #     return None, await task_func(*args, **kwargs)
    # if not hasattr(task_func, "apply"):
    #     raise ValueError(f"Task function {task_func} does not have an apply method")
    # task = task_func.apply(args=args, kwargs=kwargs)
    # result = task.get()
    # return task.id, result
    # So we need to mock the task function to return a task object
    # and then mock the task object to return a result
    # maybe a named tuple would be better here
    task = namedtuple("task", ["id", "get"])
    mock_process_graph_cached_task.apply = lambda *args, **kwargs: task(
        id="task_id_mock", get=lambda: Result(result={}, session_id="session_id_mock")
    )

    def mock_update_total_uses(*args, **kwargs):
        return created_api_key

    monkeypatch.setattr(endpoints, "process_graph_cached", mock_process_graph_cached)
    monkeypatch.setattr(crud, "update_total_uses", mock_update_total_uses)
    monkeypatch.setattr(endpoints, "process_graph_cached_task", mock_process_graph_cached_task)

    api_key = created_api_key.api_key
    headers = {"x-api-key": api_key}

    # Dummy POST data
    post_data = {
        "inputs": {"input": "value"},
        "tweaks": None,
        "clear_cache": False,
        "session_id": None,
    }

    # Make the request to the FastAPI TestClient

    response = client.post(f"api/v1/process/{flow.id}", headers=headers, json=post_data)

    # Check the response
    assert response.status_code == 200, response.json()
    assert response.json()["result"] == {}, response.json()
    assert response.json()["session_id"] == "session_id_mock", response.json()


def test_process_flow_fails_autologin_off(client, flow, monkeypatch):
    # Mock de process_graph_cached
    from langflow.api.v1 import endpoints
    from langflow.services.database.models.api_key import crud

    settings_service = get_settings_service()
    settings_service.auth_settings.AUTO_LOGIN = False

    async def mock_process_graph_cached(*args, **kwargs):
        return Result(result={}, session_id="session_id_mock")

    async def mock_update_total_uses(*args, **kwargs):
        return created_api_key

    monkeypatch.setattr(endpoints, "process_graph_cached", mock_process_graph_cached)
    monkeypatch.setattr(crud, "update_total_uses", mock_update_total_uses)

    headers = {"x-api-key": "api_key"}

    # Dummy POST data
    post_data = {
        "inputs": {"key": "value"},
        "tweaks": None,
        "clear_cache": False,
        "session_id": None,
    }

    # Make the request to the FastAPI TestClient

    response = client.post(f"api/v1/process/{flow.id}", headers=headers, json=post_data)

    # Check the response
    assert response.status_code == 403, response.json()
    assert response.json() == {"detail": "Invalid or missing API key"}


def test_get_all(client: TestClient, logged_in_headers):
    response = client.get("api/v1/all", headers=logged_in_headers)
    assert response.status_code == 200
    json_response = response.json()
    # We need to test the custom nodes
    assert "PromptTemplate" in json_response["prompts"]
    # All CUSTOM_TOOLS(dict) should be in the response
    assert all(tool in json_response["tools"] for tool in CUSTOM_TOOLS.keys())


def test_post_validate_code(client: TestClient):
    # Test case with a valid import and function
    code1 = """
import math

def square(x):
    return x ** 2
"""
    response1 = client.post("api/v1/validate/code", json={"code": code1})
    assert response1.status_code == 200
    assert response1.json() == {"imports": {"errors": []}, "function": {"errors": []}}

    # Test case with an invalid import and valid function
    code2 = """
import non_existent_module

def square(x):
    return x ** 2
"""
    response2 = client.post("api/v1/validate/code", json={"code": code2})
    assert response2.status_code == 200
    assert response2.json() == {
        "imports": {"errors": ["No module named 'non_existent_module'"]},
        "function": {"errors": []},
    }

    # Test case with a valid import and invalid function syntax
    code3 = """
import math

def square(x)
    return x ** 2
"""
    response3 = client.post("api/v1/validate/code", json={"code": code3})
    assert response3.status_code == 200
    assert response3.json() == {
        "imports": {"errors": []},
        "function": {"errors": ["expected ':' (<unknown>, line 4)"]},
    }

    # Test case with invalid JSON payload
    response4 = client.post("api/v1/validate/code", json={"invalid_key": code1})
    assert response4.status_code == 422

    # Test case with an empty code string
    response5 = client.post("api/v1/validate/code", json={"code": ""})
    assert response5.status_code == 200
    assert response5.json() == {"imports": {"errors": []}, "function": {"errors": []}}

    # Test case with a syntax error in the code
    code6 = """
import math

def square(x)
    return x ** 2
"""
    response6 = client.post("api/v1/validate/code", json={"code": code6})
    assert response6.status_code == 200
    assert response6.json() == {
        "imports": {"errors": []},
        "function": {"errors": ["expected ':' (<unknown>, line 4)"]},
    }


VALID_PROMPT = """
I want you to act as a naming consultant for new companies.

Here are some examples of good company names:

- search engine, Google
- social media, Facebook
- video sharing, YouTube

The name should be short, catchy and easy to remember.

What is a good name for a company that makes {product}?
"""

INVALID_PROMPT = "This is an invalid prompt without any input variable."


def test_valid_prompt(client: TestClient):
    PROMPT_REQUEST["template"] = VALID_PROMPT
    response = client.post("api/v1/validate/prompt", json=PROMPT_REQUEST)
    assert response.status_code == 200
    assert response.json()["input_variables"] == ["product"]


def test_invalid_prompt(client: TestClient):
    PROMPT_REQUEST["template"] = INVALID_PROMPT
    response = client.post(
        "api/v1/validate/prompt",
        json=PROMPT_REQUEST,
    )
    assert response.status_code == 200
    assert response.json()["input_variables"] == []


@pytest.mark.parametrize(
    "prompt,expected_input_variables",
    [
        ("{color} is my favorite color.", ["color"]),
        ("The weather is {weather} today.", ["weather"]),
        ("This prompt has no variables.", []),
        ("{a}, {b}, and {c} are variables.", ["a", "b", "c"]),
    ],
)
def test_various_prompts(client, prompt, expected_input_variables):
    TimeTravelGuideChainNode().to_dict()
    PROMPT_REQUEST["template"] = prompt
    response = client.post("api/v1/validate/prompt", json=PROMPT_REQUEST)
    assert response.status_code == 200
    assert response.json()["input_variables"] == expected_input_variables


def test_basic_chat_in_process(client, added_flow, created_api_key):
    # Run the /api/v1/process/{flow_id} endpoint
    headers = {"x-api-key": created_api_key.api_key}
    post_data = {"inputs": {"text": "Hi, My name is Gabriel"}}
    response = client.post(
        f"api/v1/process/{added_flow.get('id')}",
        headers=headers,
        json=post_data,
    )
    assert response.status_code == 200, response.json()
    # Check the response
    assert "Gabriel" in response.json()["result"]["text"]
    # session_id should be returned
    assert "session_id" in response.json()
    assert response.json()["session_id"] is not None
    # New request with the same session_id
    # asking "What is my name?" should return "Gabriel"
    post_data = {
        "inputs": {"text": "What is my name?"},
        "session_id": response.json()["session_id"],
    }
    response = client.post(
        f"api/v1/process/{added_flow.get('id')}",
        headers=headers,
        json=post_data,
    )
    assert response.status_code == 200, response.json()
    assert "Gabriel" in response.json()["result"]["text"]


def test_basic_chat_different_session_ids(client, added_flow, created_api_key):
    # Run the /api/v1/process/{flow_id} endpoint
    headers = {"x-api-key": created_api_key.api_key}
    post_data = {"inputs": {"text": "Hi, My name is Gabriel"}}
    response = client.post(
        f"api/v1/process/{added_flow.get('id')}",
        headers=headers,
        json=post_data,
    )
    assert response.status_code == 200, response.json()
    # Check the response
    assert "Gabriel" in response.json()["result"]["text"]
    # session_id should be returned
    assert "session_id" in response.json()
    assert response.json()["session_id"] is not None
    session_id1 = response.json()["session_id"]
    # New request with a different session_id
    # asking "What is my name?" should return "Gabriel"
    post_data = {
        "inputs": {"text": "What is my name?"},
    }
    response = client.post(
        f"api/v1/process/{added_flow.get('id')}",
        headers=headers,
        json=post_data,
    )
    assert response.status_code == 200, response.json()
    assert "Gabriel" not in response.json()["result"]["text"]
    assert session_id1 != response.json()["session_id"]


def test_basic_chat_with_two_session_ids_and_names(client, added_flow, created_api_key):
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = added_flow.get("id")
    names = ["Gabriel", "John"]
    session_ids = []

    for name in names:
        post_data = {"inputs": {"text": f"Hi, My name is {name}"}}
        response_json = run_post(client, flow_id, headers, post_data)

        assert name in response_json["result"]["text"]
        assert "session_id" in response_json
        assert response_json["session_id"] is not None

        session_ids.append(response_json["session_id"])

    for i, name in enumerate(names):
        post_data = {
            "inputs": {"text": "What is my name?"},
            "session_id": session_ids[i],
        }
        response_json = run_post(client, flow_id, headers, post_data)

        assert name in response_json["result"]["text"]


@pytest.mark.async_test
def test_vector_store_in_process(distributed_client, added_vector_store, created_api_key):
    # Run the /api/v1/process/{flow_id} endpoint
    headers = {"x-api-key": created_api_key.api_key}
    post_data = {"inputs": {"input": "What is Langflow?"}}
    response = distributed_client.post(
        f"api/v1/process/{added_vector_store.get('id')}",
        headers=headers,
        json=post_data,
    )
    assert response.status_code == 200, response.json()
    # Check the response
    assert "Langflow" in response.json()["result"]["output"]
    # session_id should be returned
    assert "session_id" in response.json()
    assert response.json()["session_id"] is not None


# Test function without loop
@pytest.mark.async_test
def test_async_task_processing(distributed_client, added_flow, created_api_key):
    headers = {"x-api-key": created_api_key.api_key}
    post_data = {"inputs": {"text": "Hi, My name is Gabriel"}}

    # Run the /api/v1/process/{flow_id} endpoint with sync=False
    response = distributed_client.post(
        f"api/v1/process/{added_flow.get('id')}",
        headers=headers,
        json={**post_data, "sync": False},
    )
    assert response.status_code == 200, response.json()

    # Extract the task ID from the response
    task = response.json().get("task")
    task_id = task.get("id")
    task_href = task.get("href")
    assert task_id is not None
    assert task_href is not None
    assert task_href == f"api/v1/task/{task_id}"

    # Polling the task status using the helper function
    task_status_json = poll_task_status(distributed_client, headers, task_href)
    assert task_status_json is not None, "Task did not complete in time"

    # Validate that the task completed successfully and the result is as expected
    assert "result" in task_status_json, task_status_json
    assert "text" in task_status_json["result"], task_status_json["result"]
    assert "Gabriel" in task_status_json["result"]["text"], task_status_json["result"]


# Test function without loop
@pytest.mark.async_test
def test_async_task_processing_vector_store(client, added_vector_store, created_api_key):
    headers = {"x-api-key": created_api_key.api_key}
    post_data = {"inputs": {"input": "How do I upload examples?"}}

    # Run the /api/v1/process/{flow_id} endpoint with sync=False
    response = client.post(
        f"api/v1/process/{added_vector_store.get('id')}",
        headers=headers,
        json={**post_data, "sync": False},
    )
    assert response.status_code == 200, response.json()
    assert "result" in response.json()
    assert "FAILURE" not in response.json()["result"]

    # Extract the task ID from the response
    task = response.json().get("task")
    task_id = task.get("id")
    task_href = task.get("href")
    assert task_id is not None
    assert task_href is not None
    assert task_href == f"api/v1/task/{task_id}"

    # Polling the task status using the helper function
    task_status_json = poll_task_status(client, headers, task_href)
    assert task_status_json is not None, "Task did not complete in time"

    # Validate that the task completed successfully and the result is as expected
    assert "result" in task_status_json, task_status_json
    assert "output" in task_status_json["result"], task_status_json["result"]
    assert "Langflow" in task_status_json["result"]["output"], task_status_json["result"]

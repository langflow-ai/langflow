import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.custom.directory_reader.directory_reader import DirectoryReader
from langflow.services.deps import get_settings_service


async def run_post(client, flow_id, headers, post_data):
    response = await client.post(
        f"api/v1/process/{flow_id}",
        headers=headers,
        json=post_data,
    )
    assert response.status_code == 200, response.json()
    return response.json()


# Helper function to poll task status
async def poll_task_status(client, headers, href, max_attempts=20, sleep_time=1):
    for _ in range(max_attempts):
        task_status_response = await client.get(
            href,
            headers=headers,
        )
        if task_status_response.status_code == 200 and task_status_response.json()["status"] == "SUCCESS":
            return task_status_response.json()
        await asyncio.sleep(sleep_time)
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
                            "gpt-4-turbo-preview",
                            "gpt-4-0125-preview",
                            "gpt-4-1106-preview",
                            "gpt-4-vision-preview",
                            "gpt-3.5-turbo-0125",
                            "gpt-3.5-turbo-1106",
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


@pytest.mark.benchmark
async def test_get_all(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/all", headers=logged_in_headers)
    assert response.status_code == 200
    settings = get_settings_service().settings
    dir_reader = DirectoryReader(settings.components_path[0])
    files = dir_reader.get_files()
    # json_response is a dict of dicts
    all_names = [component_name for _, components in response.json().items() for component_name in components]
    json_response = response.json()
    # We need to test the custom nodes
    assert len(all_names) <= len(
        files
    )  # Less or equal because we might have some files that don't have the dependencies installed
    assert "ChatInput" in json_response["inputs"]
    assert "Prompt" in json_response["prompts"]
    assert "ChatOutput" in json_response["outputs"]


async def test_post_validate_code(client: AsyncClient):
    # Test case with a valid import and function
    code1 = """
import math

def square(x):
    return x ** 2
"""
    response1 = await client.post("api/v1/validate/code", json={"code": code1})
    assert response1.status_code == 200
    assert response1.json() == {"imports": {"errors": []}, "function": {"errors": []}}

    # Test case with an invalid import and valid function
    code2 = """
import non_existent_module

def square(x):
    return x ** 2
"""
    response2 = await client.post("api/v1/validate/code", json={"code": code2})
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
    response3 = await client.post("api/v1/validate/code", json={"code": code3})
    assert response3.status_code == 200
    assert response3.json() == {
        "imports": {"errors": []},
        "function": {"errors": ["expected ':' (<unknown>, line 4)"]},
    }

    # Test case with invalid JSON payload
    response4 = await client.post("api/v1/validate/code", json={"invalid_key": code1})
    assert response4.status_code == 422

    # Test case with an empty code string
    response5 = await client.post("api/v1/validate/code", json={"code": ""})
    assert response5.status_code == 200
    assert response5.json() == {"imports": {"errors": []}, "function": {"errors": []}}

    # Test case with a syntax error in the code
    code6 = """
import math

def square(x)
    return x ** 2
"""
    response6 = await client.post("api/v1/validate/code", json={"code": code6})
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


async def test_valid_prompt(client: AsyncClient):
    PROMPT_REQUEST["template"] = VALID_PROMPT
    response = await client.post("api/v1/validate/prompt", json=PROMPT_REQUEST)
    assert response.status_code == 200
    assert response.json()["input_variables"] == ["product"]


async def test_invalid_prompt(client: AsyncClient):
    PROMPT_REQUEST["template"] = INVALID_PROMPT
    response = await client.post(
        "api/v1/validate/prompt",
        json=PROMPT_REQUEST,
    )
    assert response.status_code == 200
    assert response.json()["input_variables"] == []


@pytest.mark.parametrize(
    ("prompt", "expected_input_variables"),
    [
        ("{color} is my favorite color.", ["color"]),
        ("The weather is {weather} today.", ["weather"]),
        ("This prompt has no variables.", []),
        ("{a}, {b}, and {c} are variables.", ["a", "b", "c"]),
    ],
)
async def test_various_prompts(client, prompt, expected_input_variables):
    PROMPT_REQUEST["template"] = prompt
    response = await client.post("api/v1/validate/prompt", json=PROMPT_REQUEST)
    assert response.status_code == 200
    assert response.json()["input_variables"] == expected_input_variables


async def test_get_vertices_flow_not_found(client, logged_in_headers):
    uuid = uuid4()
    response = await client.post(f"/api/v1/build/{uuid}/vertices", headers=logged_in_headers)
    assert response.status_code == 500


async def test_get_vertices(client, added_flow_webhook_test, logged_in_headers):
    flow_id = added_flow_webhook_test["id"]
    response = await client.post(f"/api/v1/build/{flow_id}/vertices", headers=logged_in_headers)
    assert response.status_code == 200
    assert "ids" in response.json()
    # The response should contain the list in this order
    # ['ConversationBufferMemory-Lu2Nb', 'PromptTemplate-5Q0W8', 'ChatOpenAI-vy7fV', 'LLMChain-UjBh1']
    # The important part is before the - (ConversationBufferMemory, PromptTemplate, ChatOpenAI, LLMChain)
    ids = [_id.split("-")[0] for _id in response.json()["ids"]]

    assert set(ids) == {"ChatInput", "Webhook"}


async def test_build_vertex_invalid_flow_id(client, logged_in_headers):
    uuid = uuid4()
    response = await client.post(f"/api/v1/build/{uuid}/vertices/vertex_id", headers=logged_in_headers)
    assert response.status_code == 500


async def test_build_vertex_invalid_vertex_id(client, added_flow_webhook_test, logged_in_headers):
    flow_id = added_flow_webhook_test["id"]
    response = await client.post(f"/api/v1/build/{flow_id}/vertices/invalid_vertex_id", headers=logged_in_headers)
    assert response.status_code == 500


async def test_successful_run_no_payload(client, simple_api_test, created_api_key):
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]
    response = await client.post(f"/api/v1/run/{flow_id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    # Add more assertions here to validate the response content
    json_response = response.json()
    assert "session_id" in json_response
    assert "outputs" in json_response
    outer_outputs = json_response["outputs"]
    assert len(outer_outputs) == 1
    outputs_dict = outer_outputs[0]
    assert len(outputs_dict) == 2
    assert "inputs" in outputs_dict
    assert "outputs" in outputs_dict
    assert outputs_dict.get("inputs") == {"input_value": ""}
    assert isinstance(outputs_dict.get("outputs"), list)
    assert len(outputs_dict.get("outputs")) == 1
    ids = [output.get("component_id") for output in outputs_dict.get("outputs")]
    assert all("ChatOutput" in _id for _id in ids)
    display_names = [output.get("component_display_name") for output in outputs_dict.get("outputs")]
    assert all(name in display_names for name in ["Chat Output"])
    output_results_has_results = all("results" in output.get("results") for output in outputs_dict.get("outputs"))
    inner_results = [output.get("results") for output in outputs_dict.get("outputs")]

    assert all(result is not None for result in inner_results), (outputs_dict, output_results_has_results)


async def test_successful_run_with_output_type_text(client, simple_api_test, created_api_key):
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]
    payload = {
        "output_type": "text",
    }
    response = await client.post(f"/api/v1/run/{flow_id}", headers=headers, json=payload)
    assert response.status_code == status.HTTP_200_OK, response.text
    # Add more assertions here to validate the response content
    json_response = response.json()
    assert "session_id" in json_response
    assert "outputs" in json_response
    outer_outputs = json_response["outputs"]
    assert len(outer_outputs) == 1
    outputs_dict = outer_outputs[0]
    assert len(outputs_dict) == 2
    assert "inputs" in outputs_dict
    assert "outputs" in outputs_dict
    assert outputs_dict.get("inputs") == {"input_value": ""}
    assert isinstance(outputs_dict.get("outputs"), list)
    assert len(outputs_dict.get("outputs")) == 1
    ids = [output.get("component_id") for output in outputs_dict.get("outputs")]
    assert all("ChatOutput" in _id for _id in ids), ids
    display_names = [output.get("component_display_name") for output in outputs_dict.get("outputs")]
    assert all(name in display_names for name in ["Chat Output"]), display_names
    inner_results = [output.get("results") for output in outputs_dict.get("outputs")]
    expected_keys = ["message"]
    assert all(key in result for result in inner_results for key in expected_keys), outputs_dict


@pytest.mark.benchmark
async def test_successful_run_with_output_type_any(client, simple_api_test, created_api_key):
    # This one should have both the ChatOutput and TextOutput components
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]
    payload = {
        "output_type": "any",
    }
    response = await client.post(f"/api/v1/run/{flow_id}", headers=headers, json=payload)
    assert response.status_code == status.HTTP_200_OK, response.text
    # Add more assertions here to validate the response content
    json_response = response.json()
    assert "session_id" in json_response
    assert "outputs" in json_response
    outer_outputs = json_response["outputs"]
    assert len(outer_outputs) == 1
    outputs_dict = outer_outputs[0]
    assert len(outputs_dict) == 2
    assert "inputs" in outputs_dict
    assert "outputs" in outputs_dict
    assert outputs_dict.get("inputs") == {"input_value": ""}
    assert isinstance(outputs_dict.get("outputs"), list)
    assert len(outputs_dict.get("outputs")) == 1
    ids = [output.get("component_id") for output in outputs_dict.get("outputs")]
    assert all("ChatOutput" in _id or "TextOutput" in _id for _id in ids), ids
    display_names = [output.get("component_display_name") for output in outputs_dict.get("outputs")]
    assert all(name in display_names for name in ["Chat Output"]), display_names
    inner_results = [output.get("results") for output in outputs_dict.get("outputs")]
    expected_keys = ["message"]
    assert all(key in result for result in inner_results for key in expected_keys), outputs_dict


@pytest.mark.benchmark
async def test_successful_run_with_output_type_debug(client, simple_api_test, created_api_key):
    # This one should return outputs for all components
    # Let's just check the amount of outputs(there should be 7)
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]
    payload = {
        "output_type": "debug",
    }
    response = await client.post(f"/api/v1/run/{flow_id}", headers=headers, json=payload)
    assert response.status_code == status.HTTP_200_OK, response.text
    # Add more assertions here to validate the response content
    json_response = response.json()
    assert "session_id" in json_response
    assert "outputs" in json_response
    outer_outputs = json_response["outputs"]
    assert len(outer_outputs) == 1
    outputs_dict = outer_outputs[0]
    assert len(outputs_dict) == 2
    assert "inputs" in outputs_dict
    assert "outputs" in outputs_dict
    assert outputs_dict.get("inputs") == {"input_value": ""}
    assert isinstance(outputs_dict.get("outputs"), list)
    assert len(outputs_dict.get("outputs")) == 3


@pytest.mark.benchmark
async def test_successful_run_with_input_type_text(client, simple_api_test, created_api_key):
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]
    payload = {
        "input_type": "text",
        "output_type": "debug",
        "input_value": "value1",
    }
    response = await client.post(f"/api/v1/run/{flow_id}", headers=headers, json=payload)
    assert response.status_code == status.HTTP_200_OK, response.text
    # Add more assertions here to validate the response content
    json_response = response.json()
    assert "session_id" in json_response
    assert "outputs" in json_response
    outer_outputs = json_response["outputs"]
    assert len(outer_outputs) == 1
    outputs_dict = outer_outputs[0]
    assert len(outputs_dict) == 2
    assert "inputs" in outputs_dict
    assert "outputs" in outputs_dict
    assert outputs_dict.get("inputs") == {"input_value": "value1"}
    assert isinstance(outputs_dict.get("outputs"), list)
    assert len(outputs_dict.get("outputs")) == 3
    # Now we get all components that contain TextInput in the component_id
    text_input_outputs = [output for output in outputs_dict.get("outputs") if "TextInput" in output.get("component_id")]
    assert len(text_input_outputs) == 1
    # Now we check if the input_value is correct
    # We get text key twice because the output is now a Message
    assert all(
        output.get("results").get("text").get("text") == "value1" for output in text_input_outputs
    ), text_input_outputs


@pytest.mark.api_key_required
@pytest.mark.benchmark
async def test_successful_run_with_input_type_chat(client: AsyncClient, simple_api_test, created_api_key):
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]
    payload = {
        "input_type": "chat",
        "output_type": "debug",
        "input_value": "value1",
    }
    response = await client.post(f"/api/v1/run/{flow_id}", headers=headers, json=payload)
    assert response.status_code == status.HTTP_200_OK, response.text
    # Add more assertions here to validate the response content
    json_response = response.json()
    assert "session_id" in json_response
    assert "outputs" in json_response
    outer_outputs = json_response["outputs"]
    assert len(outer_outputs) == 1
    outputs_dict = outer_outputs[0]
    assert len(outputs_dict) == 2
    assert "inputs" in outputs_dict
    assert "outputs" in outputs_dict
    assert outputs_dict.get("inputs") == {"input_value": "value1"}
    assert isinstance(outputs_dict.get("outputs"), list)
    assert len(outputs_dict.get("outputs")) == 3
    # Now we get all components that contain TextInput in the component_id
    chat_input_outputs = [output for output in outputs_dict.get("outputs") if "ChatInput" in output.get("component_id")]
    assert len(chat_input_outputs) == 1
    # Now we check if the input_value is correct
    assert all(
        output.get("results").get("message").get("text") == "value1" for output in chat_input_outputs
    ), chat_input_outputs


@pytest.mark.benchmark
async def test_invalid_run_with_input_type_chat(client, simple_api_test, created_api_key):
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]
    payload = {
        "input_type": "chat",
        "output_type": "debug",
        "input_value": "value1",
        "tweaks": {"Chat Input": {"input_value": "value2"}},
    }
    response = await client.post(f"/api/v1/run/{flow_id}", headers=headers, json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
    assert "If you pass an input_value to the chat input, you cannot pass a tweak with the same name." in response.text


@pytest.mark.benchmark
async def test_successful_run_with_input_type_any(client, simple_api_test, created_api_key):
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]
    payload = {
        "input_type": "any",
        "output_type": "debug",
        "input_value": "value1",
    }
    response = await client.post(f"/api/v1/run/{flow_id}", headers=headers, json=payload)
    assert response.status_code == status.HTTP_200_OK, response.text
    # Add more assertions here to validate the response content
    json_response = response.json()
    assert "session_id" in json_response
    assert "outputs" in json_response
    outer_outputs = json_response["outputs"]
    assert len(outer_outputs) == 1
    outputs_dict = outer_outputs[0]
    assert len(outputs_dict) == 2
    assert "inputs" in outputs_dict
    assert "outputs" in outputs_dict
    assert outputs_dict.get("inputs") == {"input_value": "value1"}
    assert isinstance(outputs_dict.get("outputs"), list)
    assert len(outputs_dict.get("outputs")) == 3
    # Now we get all components that contain TextInput or ChatInput in the component_id
    any_input_outputs = [
        output
        for output in outputs_dict.get("outputs")
        if "TextInput" in output.get("component_id") or "ChatInput" in output.get("component_id")
    ]
    assert len(any_input_outputs) == 2
    # Now we check if the input_value is correct
    all_result_dicts = [output.get("results") for output in any_input_outputs]
    all_message_or_text_dicts = [
        result_dict.get("message", result_dict.get("text")) for result_dict in all_result_dicts
    ]
    assert all(
        message_or_text_dict.get("text") == "value1" for message_or_text_dict in all_message_or_text_dicts
    ), any_input_outputs


async def test_invalid_flow_id(client, created_api_key):
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = "invalid-flow-id"
    response = await client.post(f"/api/v1/run/{flow_id}", headers=headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = UUID(int=0)
    response = await client.post(f"/api/v1/run/{flow_id}", headers=headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    # Check if the error detail is as expected


@pytest.mark.benchmark
async def test_starter_projects(client, created_api_key):
    headers = {"x-api-key": created_api_key.api_key}
    response = await client.get("api/v1/starter-projects/", headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text

import inspect
import os
from unittest.mock import MagicMock, patch

import httpx
import pytest
from dotenv import load_dotenv
from langflow.load import run_flow_from_json
from langflow.load.utils import GET_FLOW_ERROR_BODY_LIMIT, GET_FLOW_TIMEOUT, get_flow
from lfx.load.utils import UploadError


def test_run_flow_from_json_params():
    # Define the expected parameters
    expected_params = {
        "flow",
        "input_value",
        "session_id",
        "tweaks",
        "input_type",
        "output_type",
        "output_component",
        "log_level",
        "log_file",
        "env_file",
        "cache",
        "disable_logs",
        "fallback_to_env_vars",
    }

    # Check if the function accepts all expected parameters
    func_spec = inspect.getfullargspec(run_flow_from_json)
    params = func_spec.args + func_spec.kwonlyargs
    assert expected_params.issubset(params), "Not all expected parameters are present in run_flow_from_json"

    # TODO: Add tests by loading a flow and running it need to text with fake llm and check if it
    # returns the correct output


@pytest.fixture
def fake_env_file(tmp_path):
    # Create a fake .env file
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_OP=TESTWORKS", encoding="utf-8")
    return env_file


def test_run_flow_with_fake_env(fake_env_file):
    # Load the flow from the JSON file
    # flow_file = Path("src/backend/tests/data/env_variable_test.json")
    flow_file = pytest.ENV_VARIABLE_TEST
    tweaks_dict = {"Secret-zIbKs": {"secret_key_input": "TEST_OP"}}

    # Run the flow from JSON, providing the fake env file
    result = run_flow_from_json(
        flow=flow_file,
        input_value="some_input_value",
        env_file=str(fake_env_file),  # Pass the path of the fake env file
        tweaks=tweaks_dict,
    )
    # Extract and check the output data
    output_data = result[0].outputs[0].results["message"].data["text"]
    assert output_data == "**********"


def test_run_flow_with_fake_env_tweaks(fake_env_file):
    # Load the flow from the JSON file
    # flow_file = Path("src/backend/tests/data/env_variable_test.json")
    flow_file = pytest.ENV_VARIABLE_TEST

    # Load env file and set up tweaks

    load_dotenv(str(fake_env_file))
    tweaks = {
        "Secret-zIbKs": {"secret_key_input": os.environ["TEST_OP"]},
    }
    # Run the flow from JSON without passing the env_file
    result = run_flow_from_json(
        flow=flow_file,
        input_value="some_input_value",
        tweaks=tweaks,
    )
    # Extract and check the output data
    output_data = result[0].outputs[0].results["message"].data["text"]
    assert output_data == "**********"


def test_get_flow_uses_bounded_http_timeout():
    response = MagicMock()
    response.status_code = httpx.codes.OK
    response.json.return_value = {"name": "Remote Flow"}

    with patch("langflow.load.utils.httpx.get", return_value=response) as mock_get:
        result = get_flow("http://host", "flow-1")

    assert result["name"] == "Remote Flow"
    _args, kwargs = mock_get.call_args
    assert kwargs["timeout"] == GET_FLOW_TIMEOUT


def test_get_flow_raises_upload_error_with_response_body_on_http_error():
    response = MagicMock()
    response.status_code = httpx.codes.INTERNAL_SERVER_ERROR
    response.text = "database unavailable"

    with patch("langflow.load.utils.httpx.get", return_value=response), pytest.raises(UploadError) as exc_info:
        get_flow("http://host", "flow-1")

    message = str(exc_info.value)
    assert "500" in message
    assert "database unavailable" in message


def test_get_flow_raises_upload_error_on_timeout():
    with (
        patch("langflow.load.utils.httpx.get", side_effect=httpx.ReadTimeout("slow host")),
        pytest.raises(UploadError) as exc_info,
    ):
        get_flow("http://host", "flow-1")

    assert "timed out" in str(exc_info.value)


def test_get_flow_truncates_large_response_body_in_error():
    response = MagicMock()
    response.status_code = httpx.codes.INTERNAL_SERVER_ERROR
    response.text = "x" * (GET_FLOW_ERROR_BODY_LIMIT * 10)

    with patch("langflow.load.utils.httpx.get", return_value=response), pytest.raises(UploadError) as exc_info:
        get_flow("http://host", "flow-1")

    message = str(exc_info.value)
    assert "truncated" in message
    # Body portion is capped; the full 5000-char payload is not embedded verbatim.
    assert len(message) < len(response.text)

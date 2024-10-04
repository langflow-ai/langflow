import pytest
import os
from dotenv import load_dotenv
from langflow.load import run_flow_from_json


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
    params = run_flow_from_json.__code__.co_varnames[: run_flow_from_json.__code__.co_argcount]
    assert expected_params.issubset(params), "Not all expected parameters are present in run_flow_from_json"

    # TODO: Add tests by loading a flow and running it need to text with fake llm and check if it returns the correct output


@pytest.fixture
def fake_env_file(tmp_path):
    # Create a fake .env file
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_OP=TESTWORKS")
    return env_file


def test_run_flow_with_fake_env(fake_env_file):
    # Load the flow from the JSON file
    # flow_file = Path("src/backend/tests/data/env_variable_test.json")
    flow_file = pytest.ENV_VARIABLE_TEST
    TWEAKS = {"Secret-zIbKs": {"secret_key_input": "TEST_OP"}}

    # Run the flow from JSON, providing the fake env file
    result = run_flow_from_json(
        flow=flow_file,
        input_value="some_input_value",
        env_file=str(fake_env_file),  # Pass the path of the fake env file
        tweaks=TWEAKS,
    )
    # Extract and check the output data
    output_data = result[0].outputs[0].results["message"].data["text"]
    assert output_data == "TESTWORKS"


def test_run_flow_with_fake_env_TWEAKS(fake_env_file):
    # Load the flow from the JSON file
    # flow_file = Path("src/backend/tests/data/env_variable_test.json")
    flow_file = pytest.ENV_VARIABLE_TEST

    # Load env file and set up tweaks

    load_dotenv(str(fake_env_file))
    TWEAKS = {
        "Secret-zIbKs": {"secret_key_input": os.environ["TEST_OP"]},
    }
    # Run the flow from JSON without passing the env_file
    result = run_flow_from_json(
        flow=flow_file,
        input_value="some_input_value",
        tweaks=TWEAKS,
    )
    # Extract and check the output data
    output_data = result[0].outputs[0].results["message"].data["text"]
    assert output_data == "TESTWORKS"

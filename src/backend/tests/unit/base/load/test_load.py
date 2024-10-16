import inspect

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
    func_spec = inspect.getfullargspec(run_flow_from_json)
    params = func_spec.args + func_spec.kwonlyargs
    assert expected_params.issubset(params), "Not all expected parameters are present in run_flow_from_json"

    # TODO: Add tests by loading a flow and running it need to text with fake llm and check if it returns the correct output

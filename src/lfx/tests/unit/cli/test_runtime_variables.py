import json

from lfx.cli.runtime_variables import build_request_variables_from_global_vars
from lfx.services.variable.service import VariableService


def test_build_request_variables_parses_langflow_request_variables():
    merged = {"access_token": "from-json", "USER_ID": "u1"}
    global_vars = {
        "LANGFLOW_REQUEST_VARIABLES": json.dumps(merged),
        "access_token": "from-raw-override",
        "x-langflow-global-var-access-token": "alias-value",
    }
    flat = build_request_variables_from_global_vars(global_vars)
    assert flat["access_token"] == "from-raw-override"
    assert flat["USER_ID"] == "u1"
    assert flat["x-langflow-global-var-access-token"] == "alias-value"


async def test_variable_service_reads_active_request_scope():
    service = VariableService()
    from lfx.services.variable.request_scope import activate_request_variables, reset_request_variables

    token = activate_request_variables(
        {
            "wxo_github_access_token": "tok-123",
            "x-langflow-global-var-wxo-github-access-token": "tok-123",
        }
    )
    try:
        assert await service.get_variable("wxo_github_access_token") == "tok-123"
        assert await service.get_variable("access_token") is None
    finally:
        reset_request_variables(token)

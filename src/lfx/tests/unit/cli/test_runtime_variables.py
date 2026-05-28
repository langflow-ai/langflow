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
    assert flat["access_token"] == "from-raw-override"  # noqa: S105  # test value, not a credential
    assert flat["USER_ID"] == "u1"
    assert flat["x-langflow-global-var-access-token"] == "alias-value"


def test_build_request_variables_keeps_raw_keys_when_blob_is_malformed():
    """A malformed LANGFLOW_REQUEST_VARIABLES blob is skipped; raw keys still merge."""
    global_vars = {
        "LANGFLOW_REQUEST_VARIABLES": "{not valid json",
        "access_token": "raw-tok",
    }
    flat = build_request_variables_from_global_vars(global_vars)
    assert flat == {"access_token": "raw-tok"}


def test_build_request_variables_ignores_non_dict_blob():
    """A JSON blob that is not an object is ignored; raw keys still merge."""
    global_vars = {
        "LANGFLOW_REQUEST_VARIABLES": json.dumps(["a", "b"]),
        "access_token": "raw-tok",
    }
    flat = build_request_variables_from_global_vars(global_vars)
    assert flat == {"access_token": "raw-tok"}


def test_reset_request_variables_restores_previous_scope():
    """Nested activate/reset restores the prior scope, not None."""
    from lfx.services.variable.request_scope import (
        activate_request_variables,
        get_active_request_variables,
        reset_request_variables,
    )

    outer = activate_request_variables({"A": "1"})
    try:
        inner = activate_request_variables({"A": "2"})
        try:
            assert get_active_request_variables() == {"A": "2"}
        finally:
            reset_request_variables(inner)
        assert get_active_request_variables() == {"A": "1"}
    finally:
        reset_request_variables(outer)
    assert get_active_request_variables() is None


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

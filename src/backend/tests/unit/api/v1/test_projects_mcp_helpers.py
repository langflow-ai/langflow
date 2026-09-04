from unittest.mock import patch

from langflow.api.v1.projects_mcp_helpers import _server_config_matches_project_auth


def _project_server_config(url: str, *, pinned: bool, api_key: bool = False) -> dict:
    args = ["--with", "mcp~=1.28"] if pinned else []
    args.extend(["mcp-proxy", "--transport", "streamablehttp"])
    if api_key:
        args.extend(["--headers", "x-api-key", "test-key"])
    args.append(url)
    return {"command": "uvx", "args": args}


def test_existing_project_config_without_sdk_constraint_requires_reconciliation():
    url = "http://localhost:7860/api/v1/mcp/project/test/streamable"

    with patch(
        "langflow.api.utils.mcp.config_utils.mcp_sdk_constraint_args",
        return_value=["--with", "mcp~=1.28"],
    ):
        assert (
            _server_config_matches_project_auth(
                _project_server_config(url, pinned=False),
                "none",
                url,
            )
            is False
        )
        assert (
            _server_config_matches_project_auth(
                _project_server_config(url, pinned=True),
                "none",
                url,
            )
            is True
        )


def test_existing_apikey_config_without_sdk_constraint_requires_reconciliation():
    url = "http://localhost:7860/api/v1/mcp/project/test/streamable"

    with patch(
        "langflow.api.utils.mcp.config_utils.mcp_sdk_constraint_args",
        return_value=["--with", "mcp~=1.28"],
    ):
        assert (
            _server_config_matches_project_auth(
                _project_server_config(url, pinned=False, api_key=True),
                "apikey",
                url,
            )
            is False
        )
        assert (
            _server_config_matches_project_auth(
                _project_server_config(url, pinned=True, api_key=True),
                "apikey",
                url,
            )
            is True
        )
